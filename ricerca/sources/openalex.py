from __future__ import annotations

import httpx

from ..config import Config
from ..i18n import strings
from ..models import Work
from .base import Source, clean

API = "https://api.openalex.org/works"


class OpenAlex(Source):
    id = "openalex"
    label = "OpenAlex"
    homepage = "https://openalex.org"

    def avviso(self, config: Config, lang: str | None = None) -> str | None:
        # Senza chiave si finisce nella corsia anonima, limitata e a budget.
        return None if config.openalex_api_key else strings(lang)["openalex_budget"]

    async def search(self, client: httpx.AsyncClient, query: str, limit: int, config: Config, filtri=None):
        pezzi = [f"title_and_abstract.search:{query}"]
        if filtri and filtri.anno_da:
            pezzi.append(f"from_publication_date:{filtri.anno_da}-01-01")
        if filtri and filtri.anno_a:
            pezzi.append(f"to_publication_date:{filtri.anno_a}-12-31")
        if filtri and filtri.solo_articoli:
            pezzi.append("type:article")
        params = {
            "filter": ",".join(pezzi),
            "per_page": str(min(limit, 50)),
            "select": "id,doi,title,publication_year,authorships,primary_location,best_oa_location,open_access,locations",
        }
        if config.mailto_valido:
            params["mailto"] = config.mailto_valido
        if config.openalex_api_key:
            params["api_key"] = config.openalex_api_key
        response = await client.get(API, params=params, timeout=25)
        response.raise_for_status()
        return [_work(item) for item in response.json().get("results", [])]


def _pdf_candidati(item: dict) -> list[str]:
    """Il PDF migliore prima, poi le altre copie, infine il collegamento di
    accesso aperto — che a volte è già il file, a volte una pagina."""

    candidati = []
    for luogo in [item.get("best_oa_location"), *(item.get("locations") or [])]:
        indirizzo = (luogo or {}).get("pdf_url")
        if indirizzo:
            candidati.append(indirizzo)
    aperto = (item.get("open_access") or {}).get("oa_url")
    if aperto:
        candidati.append(aperto)
    return candidati


def _work(item: dict) -> Work:
    location = item.get("primary_location") or {}
    venue = (location.get("source") or {}).get("display_name")
    candidati = _pdf_candidati(item)
    return Work(
        title=clean(item.get("title")) or "(senza titolo)",
        authors=[
            a["author"]["display_name"]
            for a in item.get("authorships", [])
            if a.get("author", {}).get("display_name")
        ],
        year=item.get("publication_year"),
        doi=clean(item.get("doi")),
        venue=clean(venue),
        url=clean(item.get("id")),
        oa_url=candidati[0] if candidati else None,
        oa_urls=candidati[1:],
        sources=["openalex"],
    )
