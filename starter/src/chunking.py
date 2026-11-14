"""Fixed-size and structure-aware chunking."""
import re
from .models import Chunk, DocumentPage


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("size must be positive and overlap must be in [0, size)")
    chunks: list[Chunk] = []
    step = size - overlap
    for start in range(0, len(page.text), step):
        text = page.text[start:start + size].strip()
        if text:
            chunks.append(Chunk(f"{page.document_id}:{page.page}:fixed:{start}", page.document_id,
                                page.source, page.page, text, {**page.metadata, "start": start, "end": start + len(text)}))
        if start + size >= len(page.text):
            break
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page.text) if p.strip()]
    chunks: list[Chunk] = []
    current = ""
    ordinal = 0
    for paragraph in paragraphs:
        pieces = [paragraph[i:i + max_size] for i in range(0, len(paragraph), max_size)]
        for piece in pieces:
            if current and len(current) + 2 + len(piece) > max_size:
                chunks.append(Chunk(f"{page.document_id}:{page.page}:paragraph:{ordinal}", page.document_id,
                                    page.source, page.page, current, {**page.metadata, "ordinal": ordinal}))
                ordinal += 1
                current = ""
            current = f"{current}\n\n{piece}".strip()
    if current:
        chunks.append(Chunk(f"{page.document_id}:{page.page}:paragraph:{ordinal}", page.document_id,
                            page.source, page.page, current, {**page.metadata, "ordinal": ordinal}))
    return chunks
