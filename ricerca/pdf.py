"""Scaricamento dei PDF ad accesso aperto in ~/.ricerca/pdf.

Solo i record che portano un link aperto (`oa_url`) sono scaricabili: qui non
si aggira nessun paywall.
"""

from __future__ import annotations

import hashlib
import re

import httpx

from . import biblioteca
from . import config as config_module
from .export import cite_key
from .models import Work

MAX_BYTE = 60 * 1024 * 1024
_NON_FILE = re.compile(r"[^A-Za-z0-9._-]+")


def cartella():
    percorso = config_module.CONFIG_DIR / "pdf"
    percorso.mkdir(parents=True, exist_ok=True)
    return percorso


def nome_file(work: Work) -> str:
    chiave = _NON_FILE.sub("-", cite_key(work, set()))
    firma = hashlib.sha1((work.doi or work.title).encode("utf-8")).hexdigest()[:6]
    return f"{chiave}-{firma}.pdf"


def gia_scaricato(work: Work):
    percorso = config_module.CONFIG_DIR / "pdf" / nome_file(work)
    return percorso if percorso.exists() else None


async def scarica(work: Work, client: httpx.AsyncClient):
    """Scarica il PDF aperto del record. Solleva se il file non è un PDF."""

    if not work.oa_url:
        raise ValueError("nessun link ad accesso aperto")

    esistente = gia_scaricato(work)
    if esistente:
        return esistente

    response = await client.get(work.oa_url, timeout=60, follow_redirects=True)
    response.raise_for_status()
    contenuto = response.content
    if not contenuto.startswith(b"%PDF"):
        raise ValueError("la risposta non è un PDF")
    if len(contenuto) > MAX_BYTE:
        raise ValueError("file troppo grande")

    percorso = cartella() / nome_file(work)
    percorso.write_bytes(contenuto)
    biblioteca.estrai(percorso)  # il testo serve per cercare dentro i PDF
    return percorso
