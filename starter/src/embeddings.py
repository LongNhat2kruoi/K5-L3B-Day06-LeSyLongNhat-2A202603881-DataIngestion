"""Embedding provider adapter. Uses a real OpenAI-compatible API."""
import json
import os
from urllib.request import Request, urlopen
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """OpenAI-compatible embeddings; failures are raised, never replaced by mocks."""

    def __init__(self, model_name: str, api_key: str | None = None, base_url: str | None = None) -> None:
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        default_base = "https://openrouter.ai/api/v1" if os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY") else "https://api.openai.com/v1"
        self.base_url = (base_url or os.getenv("EMBEDDING_BASE_URL") or default_base).rstrip("/")
        if not self.api_key:
            raise RuntimeError("An API key is required; configure OPENAI_API_KEY or OPENROUTER_API_KEY")
        self.dimensions = 0

    def _call(self, inputs: list[str]) -> list[list[float]]:
        request = Request(self.base_url + "/embeddings", data=json.dumps({"model": self.model_name, "input": inputs}).encode(),
                          headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=120) as response:
            payload = json.load(response)
        vectors = [row["embedding"] for row in sorted(payload["data"], key=lambda row: row["index"])]
        if not vectors:
            raise RuntimeError("Embedding provider returned no vectors")
        self.dimensions = len(vectors[0])
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._call(texts)

    def embed_query(self, question: str) -> list[float]:
        return self._call([question])[0]
