from __future__ import annotations

import httpx

from ..config import Config
from ..models import Strategy, Work
from ..strategy import or_group
from .base import Source, clean, testo

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


class EuropePMC(Source):
    id = "europepmc"
    label = "Europe PMC"
    homepage = "https://europepmc.org"

    def render_query(self, strategy: Strategy) -> str:
        groups = [
            or_group(b.clean_terms(), 'TITLE_ABS:"{term}"') for b in strategy.non_empty_blocks()
        ]
        if not groups:
            return ""
        return " AND ".join(f"({g})" for g in groups) + self.render_filtri(strategy)

    def render_filtri(self, strategy: Strategy) -> str:
        filtri, coda = strategy.filtri, ""
        if filtri.anno_da or filtri.anno_a:
            coda += f" AND (PUB_YEAR:[{filtri.anno_da or 1800} TO {filtri.anno_a or 3000}])"
        if filtri.solo_articoli:
            coda += ' AND (PUB_TYPE:"Journal Article")'
        return coda

    async def search(self, client: httpx.AsyncClient, query: str, limit: int, config: Config, filtri=None):
        params = {
            "query": query,
            "format": "json",
            "pageSize": str(min(limit, 100)),
            "resultType": "core",
        }
        response = await client.get(API, params=params, timeout=25)
        response.raise_for_status()
        results = response.json().get("resultList", {}).get("result", [])
        return [_work(item) for item in results]


def _venue(item: dict) -> str | None:
    """`bookOrReportDetails` e' un oggetto: prendine solo l'editore."""

    journal = clean(item.get("journalTitle"))
    if journal:
        return journal
    details = item.get("bookOrReportDetails")
    if isinstance(details, dict):
        return clean(details.get("publisher"))
    return clean(details)


def _work(item: dict) -> Work:
    authors = [a.strip() for a in str(item.get("authorString", "")).split(",") if a.strip()]
    year = item.get("pubYear")
    doi = clean(item.get("doi"))
    return Work(
        title=clean(item.get("title")) or "(senza titolo)",
        authors=authors,
        year=int(year) if str(year).isdigit() else None,
        doi=doi,
        venue=_venue(item),
        url=f"https://europepmc.org/article/{item.get('source', 'MED')}/{item.get('id', '')}",
        abstract=testo(item.get("abstractText")),
        sources=["europepmc"],
    )
