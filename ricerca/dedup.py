"""Fusione dei risultati provenienti da fonti diverse."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

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
    # Senza DOI l'anno fa parte della chiave: due lavori omonimi di annate
    # diverse sono lavori diversi. I casi vicini li prende il secondo giro.
    return f"title:{normalize_title(work.title)}|{work.year or ''}"


SOMIGLIANZA_MINIMA = 0.92


def _unisci(kept: Work, work: Work) -> None:
    for campo in ("doi", "year", "venue", "url", "abstract", "oa_url", "openalex_id", "pdf_archivio", "citazioni"):
        if not getattr(kept, campo) and getattr(work, campo):
            setattr(kept, campo, getattr(work, campo))
    # Un ritiro visto da una fonte sola vale per il record intero.
    kept.ritirato = kept.ritirato or work.ritirato
    kept.molto_citato = kept.molto_citato or work.molto_citato
    if len(work.authors) > len(kept.authors):
        kept.authors = work.authors
    for source in work.sources:
        if source not in kept.sources:
            kept.sources.append(source)
    kept.punteggio += work.punteggio


def somiglianza(uno: str, altro: str) -> float:
    return SequenceMatcher(None, uno, altro).ratio()


def _stesso_lavoro(uno: Work, altro: Work) -> bool:
    """Titoli quasi uguali e anni compatibili: è lo stesso lavoro.

    Serve per i titoli che una fonte tronca o punteggia diversamente, dove
    il confronto esatto fallisce.
    """

    if uno.year and altro.year and abs(uno.year - altro.year) > 1:
        return False
    titolo_uno, titolo_altro = normalize_title(uno.title), normalize_title(altro.title)
    if min(len(titolo_uno), len(titolo_altro)) < 25:
        return False  # titoli cortissimi: troppo rischioso
    if titolo_uno.startswith(titolo_altro) or titolo_altro.startswith(titolo_uno):
        return True
    return somiglianza(titolo_uno, titolo_altro) >= SOMIGLIANZA_MINIMA


def merge(works: list[Work]) -> list[Work]:
    """Unisce i duplicati tenendo il record piu' completo."""

    merged: dict[str, Work] = {}
    senza_doi: list[Work] = []
    for work in works:
        key = _key(work)
        if key in merged:
            _unisci(merged[key], work)
            continue
        merged[key] = work
        if not normalize_doi(work.doi):
            senza_doi.append(work)

    # Secondo giro solo fra i record senza DOI: lì i titoli sono l'unica presa.
    scartati: set[int] = set()
    for indice, work in enumerate(senza_doi):
        if id(work) in scartati:
            continue
        for altro in senza_doi[indice + 1 :]:
            if id(altro) in scartati or work is altro:
                continue
            if _stesso_lavoro(work, altro):
                _unisci(work, altro)
                scartati.add(id(altro))

    return [w for w in merged.values() if id(w) not in scartati]
