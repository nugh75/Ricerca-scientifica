"""Esecuzione delle query sulle fonti, in parallelo e isolate fra loro."""

from __future__ import annotations

import asyncio

import httpx

from . import sources as sources_registry
from .config import Config
from .cache import client as client_con_cache
from .dedup import merge
from .i18n import strings
from .keywords import messaggio_api
from .models import SourceResult, Strategy, Work

USER_AGENT = "ricerca/0.1 (assistente di strategia bibliografica)"


def queries_for(strategy: Strategy) -> dict[str, str]:
    """Stringa di ricerca per ogni motore registrato."""

    return {source.id: source.render_query(strategy) for source in sources_registry.ALL}


async def run(
    strategy: Strategy,
    source_ids: list[str],
    limit: int,
    config: Config,
    client: httpx.AsyncClient | None = None,
) -> tuple[list[SourceResult], list[Work]]:
    """Interroga le fonti scelte; una fonte che fallisce non ferma le altre."""

    chosen = [
        sources_registry.BY_ID[sid]
        for sid in source_ids
        if sid in sources_registry.BY_ID and sources_registry.BY_ID[sid].executable
    ]
    if not chosen or strategy.is_empty():
        return [], []

    owned = client is None
    client = client or client_con_cache(headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    try:
        results = await asyncio.gather(
            *(_one(source, strategy, limit, config, client) for source in chosen)
        )
    finally:
        if owned:
            await client.aclose()

    for result in results:
        assegna_pertinenza(result.works)
    works = merge([w for result in results for w in result.works])
    # Prima la pertinenza, poi l'anno: un record trovato in alto da piu'
    # fonti conta piu' di uno recente trovato da una sola.
    works.sort(key=lambda w: (-w.punteggio, -(w.year or 0), w.title.lower()))
    return list(results), works


# Costante della reciprocal rank fusion: attenua il peso delle prime
# posizioni, così una fonte sola non decide da sola l'ordine.
COSTANTE_RRF = 60


def assegna_pertinenza(works: list[Work]) -> None:
    for posizione, work in enumerate(works, start=1):
        work.punteggio = 1 / (COSTANTE_RRF + posizione)


async def _one(
    source, strategy: Strategy, limit: int, config: Config, client: httpx.AsyncClient
) -> SourceResult:
    query = source.render_query(strategy)
    result = SourceResult(source_id=source.id, label=source.label, query=query)

    t = strings(config.lang)
    reason = source.unavailable_reason(config, config.lang)
    if reason:
        result.error = reason
        return result
    if not query:
        result.error = t["err_empty_strategy"]
        return result

    for attempt in (1, 2):
        try:
            result.works = await source.search(client, query, limit, config, strategy.filtri)
            result.error = None
            return result
        except Exception as exc:  # una fonte rotta non deve fermare le altre
            result.error = _message(exc, t)
            if attempt == 1:
                await asyncio.sleep(1)
    return result


def _message(exc: Exception, t: dict[str, str]) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        spiegazione = messaggio_api(exc.response)
        codice = exc.response.status_code
        return f"HTTP {codice} — {spiegazione}" if spiegazione else f"HTTP {codice}"
    if isinstance(exc, httpx.TimeoutException):
        return t["err_timeout"]
    text = str(exc) or exc.__class__.__name__
    return text[:200]
