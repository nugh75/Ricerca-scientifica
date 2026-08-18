"""OPAC SBN (libri italiani) tramite la CLI `opac-sbn-pp-cli`, se installata.

Il servizio non espone un'API pubblica stabile: qui si riusa la CLI del
progetto bibliography-verify. Se il binario manca, la fonte resta
disattivata; se il servizio non risponde, l'errore resta confinato a
questa riga dei risultati.
"""

from __future__ import annotations

import asyncio
import json
import shutil

import httpx

from ..config import Config
from ..i18n import strings
from ..models import Strategy, Work
from ..strategy import flat_terms
from .base import Source, clean

BINARY = "opac-sbn-pp-cli"
TIMEOUT = 30


class OpacSbn(Source):
    id = "opacsbn"
    label = "OPAC SBN"
    homepage = "https://opac.sbn.it"

    def render_query(self, strategy: Strategy) -> str:
        return flat_terms(strategy, limit=6)

    def unavailable_reason(self, config: Config, lang: str | None = None) -> str | None:
        if shutil.which(BINARY) is None:
            return strings(lang)["need_opac_cli"].format(binary=BINARY)
        return None

    async def search(self, client: httpx.AsyncClient, query: str, limit: int, config: Config, filtri=None):
        binary = shutil.which(BINARY)
        if binary is None:
            raise RuntimeError(f"{BINARY} non trovato nel PATH")
        process = await asyncio.create_subprocess_exec(
            binary,
            "search-json",
            "--any",
            query,
            "--rows",
            str(min(limit, 50)),
            "--agent",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=TIMEOUT)
        except asyncio.TimeoutError:
            process.kill()
            raise RuntimeError(f"{BINARY} non ha risposto entro {TIMEOUT}s") from None
        if process.returncode != 0:
            raise RuntimeError(stderr.decode(errors="replace").strip()[:200] or "errore CLI")
        return parse(stdout.decode(errors="replace"))


def parse(payload: str) -> list[Work]:
    data = json.loads(payload or "{}")
    records = data
    if isinstance(data, dict):
        for key in ("records", "results", "docs", "items", "data"):
            if isinstance(data.get(key), list):
                records = data[key]
                break
    if not isinstance(records, list):
        return []
    return [_work(item) for item in records if isinstance(item, dict)]


def _work(item: dict) -> Work:
    year = str(item.get("year") or item.get("publicationYear") or item.get("data") or "")[:4]
    authors = item.get("author") or item.get("authors") or item.get("creator") or []
    if isinstance(authors, str):
        authors = [authors]
    bid = item.get("bid") or item.get("id") or ""
    return Work(
        title=clean(item.get("title") or item.get("titolo")) or "(senza titolo)",
        authors=[str(a) for a in authors if a],
        year=int(year) if year.isdigit() else None,
        venue=clean(item.get("publisher") or item.get("editore")),
        url=f"https://opac.sbn.it/bid/{bid}" if bid else None,
        sources=["opacsbn"],
    )
