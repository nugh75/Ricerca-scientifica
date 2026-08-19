"""Unpaywall: metadati mancanti e copie aperte, partendo dal DOI.

Le banche dati restituiscono record incompleti — manca la sede, manca
l'anno, manca soprattutto il collegamento a una copia leggibile. Unpaywall
tiene l'indice delle versioni ad accesso aperto di quasi tutti i DOI, comprese
quelle depositate nei repository quando l'editore fa pagare.

Serve un indirizzo email, quello di cortesia già chiesto per OpenAlex: è il
modo in cui riconoscono chi interroga.
"""

from __future__ import annotations

import httpx

from .config import Config
from .dedup import normalize_doi
from .models import Work

API = "https://api.unpaywall.org/v2"


class SenzaEmail(Exception):
    """Unpaywall rifiuta le richieste senza un indirizzo di contatto."""


def _autori(dati: dict) -> list[str]:
    nomi = []
    for autore in dati.get("z_authors") or []:
        nome = autore.get("raw_author_name") or " ".join(
            p for p in (autore.get("given"), autore.get("family")) if p
        )
        if nome.strip():
            nomi.append(" ".join(nome.split()))
    return nomi


async def dati(doi: str, config: Config, client: httpx.AsyncClient) -> dict:
    """Che cosa sa Unpaywall di questo DOI. Dizionario vuoto se non lo conosce."""

    if not config.mailto_valido:
        raise SenzaEmail("serve l'email di cortesia")
    pulito = normalize_doi(doi)
    if not pulito:
        return {}

    risposta = await client.get(
        f"{API}/{pulito}", params={"email": config.mailto_valido}, timeout=25
    )
    if risposta.status_code == 404:
        return {}
    risposta.raise_for_status()
    corpo = risposta.json()

    migliore = corpo.get("best_oa_location") or {}
    return {
        "title": corpo.get("title") or "",
        "venue": corpo.get("journal_name") or "",
        "year": corpo.get("year"),
        "authors": _autori(corpo),
        "oa_url": migliore.get("url_for_pdf") or "",
        "oa_status": corpo.get("oa_status") or "",
        "editore": corpo.get("publisher") or "",
    }


def da_completare(work: Work) -> list[str]:
    """I campi che a questo record mancano e che Unpaywall può dare."""

    mancanti = []
    if not work.oa_url:
        mancanti.append("oa_url")
    if not work.venue:
        mancanti.append("venue")
    if not work.year:
        mancanti.append("year")
    if not work.authors:
        mancanti.append("authors")
    return mancanti


def completamento(work: Work, conosciuto: dict) -> dict:
    """Solo i campi davvero mancanti: quel che c'è non si tocca."""

    aggiunte = {}
    for campo in da_completare(work):
        valore = conosciuto.get(campo)
        if valore:
            aggiunte[campo] = valore
    return aggiunte
