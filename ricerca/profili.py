"""Profili bibliometrici di autori e riviste, letti da OpenAlex.

Gli identificativi vengono sempre validati prima di diventare parte di un
percorso API. I conteggi appartengono a OpenAlex e sono una fotografia utile,
non un giudizio di qualità né un valore aggiornato in tempo reale.
"""

from __future__ import annotations

import re

import httpx

from . import openalex_api
from .config import Config
from .models import Work
from .sources.openalex import SELECT, work_da

TIPI = ("autori", "riviste")
_ID = re.compile(r"^[AS]\d+$", re.IGNORECASE)
_SELECT_AUTORI = (
    "id,display_name,orcid,works_count,cited_by_count,summary_stats,"
    "last_known_institutions,counts_by_year"
)
_SELECT_RIVISTE = (
    "id,display_name,type,issn_l,works_count,cited_by_count,summary_stats,"
    "host_organization_name,is_oa,is_in_doaj,homepage_url,counts_by_year"
)


def identificativo(valore: str, prefisso: str) -> str:
    breve = openalex_api.id_breve(valore).upper()
    return breve if _ID.fullmatch(breve) and breve.startswith(prefisso.upper()) else ""


def _anni(corpo: dict) -> list[dict]:
    righe = [
        {
            "anno": int(riga.get("year") or 0),
            "lavori": int(riga.get("works_count") or 0),
            "citazioni": int(riga.get("cited_by_count") or 0),
        }
        for riga in corpo.get("counts_by_year", [])
        if str(riga.get("year") or "").isdigit()
    ]
    righe = sorted(righe, key=lambda r: r["anno"])[-10:]
    massimo = max((r["citazioni"] for r in righe), default=1) or 1
    for riga in righe:
        riga["quota"] = round(100 * riga["citazioni"] / massimo)
    return righe


def _metriche(corpo: dict) -> dict:
    statistiche = corpo.get("summary_stats") or {}
    return {
        "lavori": int(corpo.get("works_count") or 0),
        "citazioni": int(corpo.get("cited_by_count") or 0),
        "h_index": int(statistiche.get("h_index") or 0),
        "i10_index": int(statistiche.get("i10_index") or 0),
        "media_due_anni": statistiche.get("2yr_mean_citedness"),
        "anni": _anni(corpo),
    }


def da_autore(corpo: dict) -> dict:
    istituzioni = corpo.get("last_known_institutions") or []
    return {
        "tipo": "autori",
        "id": identificativo(corpo.get("id", ""), "A"),
        "nome": str(corpo.get("display_name") or ""),
        "orcid": str(corpo.get("orcid") or ""),
        "istituzione": str((istituzioni[0] if istituzioni else {}).get("display_name") or ""),
        **_metriche(corpo),
    }


def da_rivista(corpo: dict) -> dict:
    return {
        "tipo": "riviste",
        "id": identificativo(corpo.get("id", ""), "S"),
        "nome": str(corpo.get("display_name") or ""),
        "issn": str(corpo.get("issn_l") or ""),
        "editore": str(corpo.get("host_organization_name") or ""),
        "oa": bool(corpo.get("is_oa")),
        "doaj": bool(corpo.get("is_in_doaj")),
        "sito": str(corpo.get("homepage_url") or ""),
        **_metriche(corpo),
    }


async def cerca(
    tipo: str, q: str, config: Config, client: httpx.AsyncClient, limite: int = 12
) -> list[dict]:
    """Cerca profili; per le riviste esclude repository e convegni."""

    q = q.strip()
    if tipo not in TIPI or len(q) < 2:
        return []
    autori = tipo == "autori"
    corpo = await openalex_api.chiama(
        client,
        "/authors" if autori else "/sources",
        config,
        search=q,
        filter="" if autori else "type:journal",
        per_page=str(min(max(1, limite), 25)),
        select=_SELECT_AUTORI if autori else _SELECT_RIVISTE,
    )
    converti = da_autore if autori else da_rivista
    return [profilo for voce in corpo.get("results", []) if (profilo := converti(voce))["id"]]


async def leggi(
    tipo: str, id_entita: str, config: Config, client: httpx.AsyncClient
) -> tuple[dict, list[Work]]:
    """Profilo e dieci lavori più citati dell'entità."""

    autori = tipo == "autori"
    prefisso = "A" if autori else "S"
    id_pulito = identificativo(id_entita, prefisso)
    if tipo not in TIPI or not id_pulito:
        raise ValueError("identificativo OpenAlex non valido")

    corpo = await openalex_api.chiama(
        client,
        f"/{'authors' if autori else 'sources'}/{id_pulito}",
        config,
        select=_SELECT_AUTORI if autori else _SELECT_RIVISTE,
    )
    if not autori and corpo.get("type") != "journal":
        raise ValueError("la sede OpenAlex non è una rivista")
    profilo = da_autore(corpo) if autori else da_rivista(corpo)
    lavori = await openalex_api.chiama(
        client,
        "/works",
        config,
        filter=(
            f"authorships.author.id:{id_pulito}"
            if autori else f"primary_location.source.id:{id_pulito}"
        ),
        sort="cited_by_count:desc",
        per_page="10",
        select=SELECT,
    )
    return profilo, [work_da(voce) for voce in lavori.get("results", [])]
