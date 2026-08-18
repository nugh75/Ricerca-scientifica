"""Invio dei record alla libreria Zotero dell'utente.

Serve una chiave API personale e l'identificativo della libreria, entrambi
dalle impostazioni: nulla di tutto ciò sta nel codice.
"""

from __future__ import annotations

import httpx

from .config import Config
from .models import Work

API = "https://api.zotero.org"
MASSIMO_PER_INVIO = 50


class ZoteroError(Exception):
    pass


def voce(work: Work) -> dict:
    """Un record nel formato che Zotero si aspetta (`journalArticle`)."""

    autori = []
    for nome in work.authors:
        parti = nome.replace(",", " ").split()
        if len(parti) == 1:
            autori.append({"creatorType": "author", "name": parti[0]})
        else:
            autori.append(
                {"creatorType": "author", "firstName": " ".join(parti[:-1]), "lastName": parti[-1]}
            )
    return {
        "itemType": "journalArticle",
        "title": work.title,
        "creators": autori,
        "date": str(work.year or ""),
        "publicationTitle": work.venue or "",
        "DOI": (work.doi or "").replace("https://doi.org/", ""),
        "url": work.url or "",
        "abstractNote": work.abstract or "",
        "tags": [{"tag": fonte} for fonte in work.sources],
    }


async def invia(works: list[Work], config: Config, client: httpx.AsyncClient) -> dict:
    """Manda i record a Zotero. Ritorna quanti ne sono entrati e quanti no."""

    if not (config.zotero_api_key and config.zotero_library_id):
        raise ZoteroError("chiave e identificativo della libreria mancanti")
    if not works:
        return {"inviati": 0, "falliti": 0}

    tipo = config.zotero_library_type if config.zotero_library_type in ("users", "groups") else "users"
    url = f"{API}/{tipo}/{config.zotero_library_id}/items"
    intestazioni = {
        "Zotero-API-Key": config.zotero_api_key,
        "Zotero-API-Version": "3",
        "Content-Type": "application/json",
    }

    inviati = falliti = 0
    for inizio in range(0, len(works), MASSIMO_PER_INVIO):
        lotto = [voce(w) for w in works[inizio : inizio + MASSIMO_PER_INVIO]]
        risposta = await client.post(url, json=lotto, headers=intestazioni, timeout=60)
        if risposta.status_code == 403:
            raise ZoteroError("chiave rifiutata da Zotero (permessi di scrittura?)")
        risposta.raise_for_status()
        esito = risposta.json()
        inviati += len(esito.get("successful", {})) + len(esito.get("unchanged", {}))
        falliti += len(esito.get("failed", {}))
    return {"inviati": inviati, "falliti": falliti}
