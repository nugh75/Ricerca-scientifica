"""Snowballing: da un articolo trovato agli articoli che gli stanno intorno.

Tre direzioni, tutte da OpenAlex:
- **indietro**, la bibliografia dell'articolo (`referenced_works`);
- **avanti**, chi lo cita (`filter=cites:`);
- **di lato**, i lavori che OpenAlex considera vicini (`related_works`).

La scheda del singolo lavoro non costa nulla; i record veri si prendono a
blocchi di cento, il massimo di valori in OR che un filtro accetta.
"""

from __future__ import annotations

import httpx

from . import openalex_api
from .config import Config
from .models import Work
from .sources.openalex import SELECT, work_da

VERSI = ("indietro", "avanti", "lato")
BLOCCO = 100          # valori in OR ammessi da un filtro


async def cerca(
    work: Work,
    verso: str,
    config: Config,
    client: httpx.AsyncClient,
    limite: int = 50,
) -> list[Work]:
    if verso not in VERSI:
        raise ValueError(f"verso sconosciuto: {verso}")
    identificativo = work.openalex_id or openalex_api.id_breve(work.url)
    if not identificativo.startswith("W"):
        raise ValueError("questo record non ha un identificativo OpenAlex")

    if verso == "avanti":
        corpo = await openalex_api.chiama(
            client,
            "/works",
            config,
            filter=f"cites:{identificativo}",
            per_page=str(min(limite, 100)),
            select=SELECT,
            sort="cited_by_count:desc",
        )
        return [work_da(item) for item in corpo.get("results", [])]

    campo = "referenced_works" if verso == "indietro" else "related_works"
    scheda = await openalex_api.chiama(
        client, f"/works/{identificativo}", config, select=f"id,{campo}"
    )
    ids = [openalex_api.id_breve(u) for u in (scheda.get(campo) or [])]
    return await per_id(ids[:limite], config, client)


async def per_id(ids: list[str], config: Config, client: httpx.AsyncClient) -> list[Work]:
    """I record di una lista di identificativi, a blocchi di cento."""

    trovati: list[Work] = []
    for inizio in range(0, len(ids), BLOCCO):
        gruppo = [i for i in ids[inizio : inizio + BLOCCO] if i]
        if not gruppo:
            continue
        corpo = await openalex_api.chiama(
            client,
            "/works",
            config,
            filter="openalex:" + "|".join(gruppo),
            per_page=str(BLOCCO),
            select=SELECT,
        )
        trovati.extend(work_da(item) for item in corpo.get("results", []))
    return trovati
