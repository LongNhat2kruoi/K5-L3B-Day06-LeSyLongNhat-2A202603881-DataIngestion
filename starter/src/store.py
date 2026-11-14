"""PostgreSQL + pgvector storage with parameterized metadata filters."""
import json
import psycopg
from typing import Any
from .models import Chunk


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        self.database_url, self.dimensions = database_url, dimensions

    def create_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute(f"""CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id text NOT NULL, strategy text NOT NULL, document_id text NOT NULL,
                    source text NOT NULL, page text NOT NULL, text_content text NOT NULL,
                    metadata jsonb NOT NULL, embedding vector({self.dimensions}) NOT NULL,
                    PRIMARY KEY (strategy, chunk_id))""")
                cur.execute("CREATE INDEX IF NOT EXISTS chunks_metadata_idx ON chunks USING gin (metadata)")

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have equal length")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chunks WHERE strategy = %s", (strategy,))
                for chunk, vector in zip(chunks, vectors):
                    if len(vector) != self.dimensions:
                        raise ValueError(f"Embedding dimension mismatch for {chunk.chunk_id}")
                    cur.execute("""INSERT INTO chunks
                        (chunk_id,strategy,document_id,source,page,text_content,metadata,embedding)
                        VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::vector)""",
                        (chunk.chunk_id, strategy, chunk.document_id, chunk.source, str(chunk.page), chunk.text,
                         json.dumps(chunk.metadata), "[" + ",".join(map(str, vector)) + "]"))

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if top_k <= 0:
            return []
        if len(query_vector) != self.dimensions:
            raise ValueError("Query embedding dimension does not match the store")
        vector = "[" + ",".join(map(str, query_vector)) + "]"
        clauses = ["strategy = %s"]
        params: list[Any] = [strategy]
        for key, value in (filters or {}).items():
            if key not in {"section", "module", "topic", "version", "language", "document_type"}:
                raise ValueError(f"Unsupported metadata filter: {key}")
            clauses.append("metadata ->> %s = %s")
            params.extend([key, str(value)])
        params.extend([vector, top_k])
        sql = f"""SELECT chunk_id, text_content, document_id, source, page, metadata,
                         1 - (embedding <=> %s::vector) AS score
                  FROM chunks WHERE {' AND '.join(clauses)}
                  ORDER BY embedding <=> %s::vector LIMIT %s"""
        # The query vector is used once in the SELECT and once in ORDER BY.
        params = [vector, *params[:-2], vector, params[-1]]
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [{"chunk_id": r[0], "text": r[1], "document_id": r[2], "source": r[3], "page": r[4], "metadata": r[5], "score": float(r[6])} for r in cur.fetchall()]
