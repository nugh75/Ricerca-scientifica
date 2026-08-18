"""Fusione dei risultati provenienti da fonti diverse."""

from __future__ import annotations

import re
import unicodedata

from .models import Work

_PUNCT = re.compile(r"[^a-z0-9 ]+")
_SPACES = re.compile(r"\s+")


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    value = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    return value.strip("/") or None


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _PUNCT.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def _key(work: Work) -> str:
    doi = normalize_doi(work.doi)
    if doi:
        return f"doi:{doi}"
    return f"title:{normalize_title(work.title)}"


def merge(works: list[Work]) -> list[Work]:
    """Unisce i duplicati tenendo il record piu' completo."""

    merged: dict[str, Work] = {}
    for work in works:
        key = _key(work)
        if key not in merged:
            merged[key] = work
            continue
        kept = merged[key]
        for field in ("doi", "year", "venue", "url", "abstract", "oa_url"):
            if not getattr(kept, field) and getattr(work, field):
                setattr(kept, field, getattr(work, field))
        if len(work.authors) > len(kept.authors):
            kept.authors = work.authors
        for source in work.sources:
            if source not in kept.sources:
                kept.sources.append(source)
    return list(merged.values())
