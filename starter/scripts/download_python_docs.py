"""Download a reproducible 30-unit Python documentation corpus.

The content comes from the official versioned Python 3.15 documentation site.
Run from starter/: python scripts/download_python_docs.py
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "https://docs.python.org/3.15/"
PAGES = [
    "tutorial/index.html", "tutorial/appetite.html", "tutorial/interpreter.html",
    "tutorial/introduction.html", "tutorial/controlflow.html", "tutorial/datastructures.html",
    "tutorial/modules.html", "tutorial/inputoutput.html", "tutorial/errors.html",
    "tutorial/classes.html", "tutorial/stdlib.html", "tutorial/stdlib2.html",
    "tutorial/venv.html", "tutorial/whatnow.html", "tutorial/interactive.html",
    "library/functions.html", "library/constants.html", "library/stdtypes.html",
    "library/exceptions.html", "library/text.html", "library/binary.html",
    "library/datatypes.html", "library/numeric.html", "library/functional.html",
    "library/itertools.html", "library/functools.html", "library/operator.html",
    "library/filesys.html", "library/os.html", "library/io.html",
]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    corpus = root / "data" / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    entries = []
    for index, relative in enumerate(PAGES, start=1):
        url = BASE + relative
        request = Request(url, headers={"User-Agent": "day6-data-ingestion-lab/1.0"})
        with urlopen(request, timeout=60) as response:
            html = response.read()
        filename = f"{index:02d}_{Path(relative).stem}.html"
        path = corpus / filename
        path.write_bytes(html)
        text = re.sub(r"<[^>]+>", " ", html.decode("utf-8", errors="replace"))
        text = re.sub(r"\s+", " ", text).strip()
        entries.append({
            "unit_id": path.stem,
            "document_id": "python-docs-3.15",
            "title": relative,
            "source_path_or_url": url,
            "license_or_permission": "Python Software Foundation License 2; see https://docs.python.org/3.15/license.html",
            "accessed_at": datetime.now(timezone.utc).isoformat(),
            "version": "3.15.2",
            "section": relative.split("/", 1)[0],
            "module": Path(relative).stem,
            "char_count_html_rough": len(text),
            "path": str(Path("data/corpus") / filename),
        })
    (root / "data" / "manifest.json").write_text(json.dumps({
        "corpus_id": "python-docs-3.15", "unit_count": len(entries), "units": entries
    }, indent=2), encoding="utf-8")
    print(f"Downloaded {len(entries)} HTML units to {corpus}")


if __name__ == "__main__":
    main()
