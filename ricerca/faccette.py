"""Com'è fatta la letteratura su un argomento, prima di leggerne un rigo.

`group_by` conta i risultati per anno, tipo, accesso, tema e paese: cinque
chiamate da $0.0001 che dicono se il campo è giovane o maturo, se è chiuso o
aperto, e da dove viene. Gli stessi numeri servono al diagramma PRISMA.
"""

from __future__ import annotations

import asyncio

import httpx

from . import openalex_api
from .config import Config
from .sources.openalex import filtro

# Campo dell'API, chiave i18n dell'etichetta.
CAMPI = (
    ("publication_year", "faccetta_anno"),
    ("type", "faccetta_tipo"),
    ("open_access.is_oa", "faccetta_accesso"),
    ("primary_topic.id", "faccetta_tema"),
    ("authorships.countries", "faccetta_paese"),
)


async def profilo(
    query: str,
    filtri,
    config: Config,
    client: httpx.AsyncClient,
    quanti: int = 12,
) -> list[dict]:
    """Un blocco per campo, con le voci già in scala per disegnare le barre."""

    stringa = filtro(query, filtri)
    esiti = await asyncio.gather(
        *(_uno(stringa, campo, config, client, quanti) for campo, _ in CAMPI),
        return_exceptions=True,
    )
    profilo = []
    for (campo, etichetta), esito in zip(CAMPI, esiti):
        voci = [] if isinstance(esito, Exception) else esito
        profilo.append({"campo": campo, "etichetta": etichetta, "voci": voci})
    return profilo


async def _uno(stringa: str, campo: str, config: Config, client, quanti: int) -> list[dict]:
    corpo = await openalex_api.chiama(
        client, "/works", config, filter=stringa, group_by=campo
    )
    gruppi = [g for g in corpo.get("group_by", []) if g.get("count")]
    gruppi.sort(key=lambda g: -g["count"])
    gruppi = gruppi[:quanti]
    massimo = gruppi[0]["count"] if gruppi else 1
    return [
        {
            "etichetta": g.get("key_display_name") or g.get("key") or "?",
            "quanti": g["count"],
            # La quota è la larghezza della barra, non una percentuale del
            # totale: serve a confrontare le voci fra loro.
            "quota": round(100 * g["count"] / massimo),
        }
        for g in gruppi
    ]
