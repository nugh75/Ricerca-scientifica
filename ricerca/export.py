"""Export dei risultati in BibTeX e CSV."""

from __future__ import annotations

import csv
import io
import re
import unicodedata

from .models import Work

_NON_WORD = re.compile(r"[^a-z0-9]+")
_STOPWORDS = {"the", "a", "an", "of", "on", "in", "and", "for", "il", "lo", "la", "di", "e"}


def cite_key(work: Work, taken: set[str]) -> str:
    author = work.authors[0].split()[-1].lower() if work.authors else "anon"
    author = _ascii(author) or "anon"
    year = str(work.year or "s.d.").replace(".", "")
    word = ""
    for candidate in _NON_WORD.split(_ascii(work.title.lower())):
        if candidate and candidate not in _STOPWORDS:
            word = candidate
            break
    base = f"{author}{year}{word}"[:40] or "ref"
    key, suffix = base, ord("a")
    while key in taken:
        key = f"{base}{chr(suffix)}"
        suffix += 1
    taken.add(key)
    return key


def to_bibtex(works: list[Work]) -> str:
    taken: set[str] = set()
    entries = []
    for work in works:
        fields = [("title", work.title)]
        if work.authors:
            fields.append(("author", " and ".join(work.authors)))
        if work.year:
            fields.append(("year", str(work.year)))
        if work.venue:
            fields.append(("journal", work.venue))
        if work.doi:
            fields.append(("doi", work.doi))
        if work.url:
            fields.append(("url", work.url))
        body = ",\n".join(f"  {name} = {{{_clean(value)}}}" for name, value in fields)
        entries.append(f"@article{{{cite_key(work, taken)},\n{body}\n}}")
    return "\n\n".join(entries) + ("\n" if entries else "")


def to_csv(works: list[Work]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["titolo", "autori", "anno", "doi", "sede", "url", "fonti"])
    for work in works:
        writer.writerow(
            [
                work.title,
                "; ".join(work.authors),
                work.year or "",
                work.doi or "",
                work.venue or "",
                work.url or "",
                "; ".join(work.sources),
            ]
        )
    return buffer.getvalue()


def _clean(value: str) -> str:
    return str(value).replace("{", "").replace("}", "").strip()


def _ascii(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    return "".join(c for c in text if not unicodedata.combining(c) and c.isascii())
