"""Read and normalize PDF/HTML source data while preserving provenance."""
from html.parser import HTMLParser
import re
import unicodedata
from pathlib import Path
from .models import DocumentPage


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    from pypdf import PdfReader
    pages: list[DocumentPage] = []
    for number, page in enumerate(PdfReader(str(path)).pages, start=1):
        text = normalize_text(page.extract_text() or "")
        pages.append(DocumentPage(document_id, source, number, text,
                                  {"document_type": "pdf", "has_text": bool(text)}))
    return pages


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer", "header"}:
            self.skip += 1
        elif not self.skip and tag in {"h1", "h2", "h3", "h4", "p", "li", "pre", "dt", "dd"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "header"} and self.skip:
            self.skip -= 1
        elif not self.skip and tag in {"h1", "h2", "h3", "h4", "p", "li", "pre", "dt", "dd"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def load_html(path: Path, document_id: str, source: str, metadata: dict | None = None) -> list[DocumentPage]:
    """Load one HTML unit as a traceable logical page."""
    parser = _TextExtractor()
    parser.feed(path.read_text(encoding="utf-8"))
    text = normalize_text("".join(parser.parts))
    return [DocumentPage(document_id, source, path.stem, text, metadata or {})]
