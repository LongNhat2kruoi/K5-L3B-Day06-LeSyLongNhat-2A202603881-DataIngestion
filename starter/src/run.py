"""Run the three controlled retrieval strategies against the local corpus."""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_html
from .store import PgVectorStore


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    manifest = json.loads((root / "data/manifest.json").read_text(encoding="utf-8"))
    questions = json.loads((root / "benchmark/questions.json").read_text(encoding="utf-8"))
    if len(manifest["units"]) < 30:
        raise ValueError("The corpus must contain at least 30 HTML units")
    if len(questions) < 20:
        raise ValueError("The benchmark must contain at least 20 questions")
    pages = []
    for unit in manifest["units"]:
        metadata = {k: unit[k] for k in ("section", "module", "version") if k in unit}
        pages.extend(load_html(root / unit["path"], unit["document_id"], unit["source_path_or_url"], metadata))
    model_name = os.getenv("EMBEDDING_MODEL", "").strip()
    if not model_name:
        raise RuntimeError(
            "EMBEDDING_MODEL is empty. Set it in starter/.env, for example "
            "EMBEDDING_MODEL=text-embedding-3-small."
        )
    if not (os.getenv("OPENAI_API_KEY", "").strip() or os.getenv("OPENROUTER_API_KEY", "").strip()):
        raise RuntimeError(
            "No embedding API key found. Set OPENAI_API_KEY or OPENROUTER_API_KEY "
            "in starter/.env. Do not commit the key."
        )
    if not os.getenv("DATABASE_URL", "").strip():
        raise RuntimeError("DATABASE_URL is empty. Copy starter/.env.example to starter/.env first.")
    embedder = MyEmbedder(model_name)
    store: PgVectorStore | None = None
    traces = []
    for strategy in ("A", "B", "C"):
        chunks = [c for page in pages for c in (
            fixed_size(page, 500, 50) if strategy == "A" else by_paragraph(page, 800)
        )]
        vectors = embedder.embed_documents([chunk.text for chunk in chunks])
        if store is None:
            store = PgVectorStore(os.environ["DATABASE_URL"], embedder.dimensions)
            store.create_schema()
        store.upsert(strategy, chunks, vectors)
        for question in questions:
            vector = embedder.embed_query(question["question"])
            filters = question.get("filter") if strategy == "C" else None
            hits = store.search(strategy, vector, 3, filters)
            trace = evaluate_query(question, hits)
            trace["strategy"] = strategy
            traces.append(trace)
    results = root / "results"
    results.mkdir(exist_ok=True)
    (results / "traces.json").write_text(json.dumps(traces, indent=2, ensure_ascii=False), encoding="utf-8")
    (results / "metrics.json").write_text(json.dumps(summarize(traces), indent=2), encoding="utf-8")
    print(json.dumps(summarize(traces), indent=2))


if __name__ == "__main__":
    main()
