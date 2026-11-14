"""Small browser demo for the Day 06 retrieval pipeline.

Run from starter/: python web_demo.py
Then open http://127.0.0.1:8000
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from src.embeddings import MyEmbedder
from src.store import PgVectorStore


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


class AppState:
    def __init__(self) -> None:
        model = os.getenv("EMBEDDING_MODEL", "").strip()
        if not model:
            raise RuntimeError("EMBEDDING_MODEL is missing in starter/.env")
        if not (os.getenv("OPENAI_API_KEY", "").strip() or os.getenv("OPENROUTER_API_KEY", "").strip()):
            raise RuntimeError("OPENAI_API_KEY or OPENROUTER_API_KEY is missing in starter/.env")
        self.embedder = MyEmbedder(model)
        self.store: PgVectorStore | None = None

    def generate_answer(self, question: str, hits: list[dict]) -> str:
        refusal = "Tài liệu hiện có không cung cấp đủ thông tin để trả lời câu hỏi này."
        if not hits:
            return refusal
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for answer generation")
        model = os.getenv("CHAT_MODEL", "openai/gpt-4o-mini")
        context = "\n\n".join(
            f"[{index}] source={hit['source']} unit={hit['page']}\n{hit['text']}"
            for index, hit in enumerate(hits, start=1)
        )
        prompt = (
            "Bạn là trợ lý hỏi đáp tài liệu có grounding. Luôn trả lời bằng tiếng Việt, "
            "kể cả khi câu hỏi hoặc evidence là tiếng Anh. Chỉ dùng thông tin được "
            "nêu trực tiếp trong evidence. Nếu evidence không trực tiếp trả lời câu hỏi, "
            "đặt supported=false và dùng đúng câu: Tài liệu hiện có không cung cấp đủ thông tin để trả lời câu hỏi này. "
            "Không dùng kiến thức bên ngoài, không suy đoán và không bịa nguồn. "
            "Trả về duy nhất JSON hợp lệ theo schema: "
            '{"supported":true|false,"answer":"...","citations":[1,2]}. '
            "Nếu supported=false, answer phải chính xác là câu từ chối và citations là [].\n\n"
            f"Câu hỏi: {question}\n\nEvidence truy xuất:\n{context}"
        )
        request = Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps({"model": model, "temperature": 0.1, "messages": [
                {"role": "system", "content": "You answer only from supplied evidence, follow the JSON schema exactly, and always use Vietnamese."},
                {"role": "user", "content": prompt},
            ]}).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://127.0.0.1:8000",
                "X-Title": "Day 06 Retrieval Demo",
            },
            method="POST",
        )
        with urlopen(request, timeout=120) as response:
            payload = json.load(response)
        content = payload["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        try:
            raw = str(content).strip()
            raw = raw.removeprefix("```json").removesuffix("```").strip()
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return refusal
        citations = parsed.get("citations", [])
        valid_citations = isinstance(citations, list) and all(
            isinstance(item, int) and 1 <= item <= len(hits) for item in citations
        )
        if parsed.get("supported") is not True or not valid_citations or not citations:
            return refusal
        answer = str(parsed.get("answer", "")).strip()
        return answer if answer else refusal

    def search(self, strategy: str, question: str, filters: dict[str, str] | None) -> list[dict]:
        vector = self.embedder.embed_query(question)
        if self.store is None:
            self.store = PgVectorStore(os.environ["DATABASE_URL"], len(vector))
        return self.store.search(strategy, vector, top_k=3, filters=filters)


STATE: AppState | None = None


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._send(200, (ROOT / "web/index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/benchmark":
            try:
                metrics = json.loads((ROOT / "results/metrics.json").read_text(encoding="utf-8"))
                questions = json.loads((ROOT / "benchmark/questions.json").read_text(encoding="utf-8"))
                traces = json.loads((ROOT / "results/traces.json").read_text(encoding="utf-8"))
                self._send(200, json.dumps({"metrics": metrics, "questions": questions, "traces": traces}, ensure_ascii=False).encode(), "application/json")
            except (FileNotFoundError, json.JSONDecodeError) as exc:
                self._send(500, json.dumps({"error": str(exc)}).encode(), "application/json")
        elif path == "/api/health":
            self._send(200, json.dumps({"ok": True, "demo_version": "generation-v1"}).encode(), "application/json")
        else:
            self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/search":
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            question = str(payload.get("question", "")).strip()
            strategy = str(payload.get("strategy", "C"))
            filters = payload.get("filters") or None
            if not question:
                raise ValueError("question is required")
            if strategy not in {"A", "B", "C"}:
                raise ValueError("strategy must be A, B or C")
            if filters and strategy != "C":
                raise ValueError("metadata filters are only enabled for strategy C")
            results = STATE.search(strategy, question, filters) if STATE else []
            answer = STATE.generate_answer(question, results) if STATE else ""
            self._send(200, json.dumps({"strategy": strategy, "results": results, "answer": answer}, ensure_ascii=False).encode(), "application/json")
        except Exception as exc:  # Return readable errors to the demo UI.
            self._send(400, json.dumps({"error": str(exc)}).encode(), "application/json")

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    global STATE
    STATE = AppState()
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Day 06 demo: http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping demo")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
