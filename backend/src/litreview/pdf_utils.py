from pathlib import Path

import requests
from pypdf import PdfReader

MIN_TEXT_CHARS = 200


class PdfDownloadError(Exception):
    pass


def download_pdf(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        raise PdfDownloadError(str(e)) from e
    dest.write_bytes(r.content)
    return dest


def extract_text(pdf_path: Path, max_pages: int = 30) -> str:
    reader = PdfReader(str(pdf_path))
    pages = reader.pages[:max_pages]
    return "\n".join(page.extract_text() or "" for page in pages)


def has_extractable_text(text: str) -> bool:
    return len(text.strip()) >= MIN_TEXT_CHARS
