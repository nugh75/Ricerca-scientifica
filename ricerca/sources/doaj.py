from __future__ import annotations

from urllib.parse import quote

import httpx

from ..config import Config
from ..models import Work
from .base import Source, clean

API = "https://doaj.org/api/search/articles"


class Doaj(Source):
    id = "doaj"
    label = "DOAJ"
    homepage = "https://doaj.org"

    def render_filtri(self, strategy) -> str:
        filtri = strategy.filtri
        if not (filtri.anno_da or filtri.anno_a):
            return ""
        return f" AND bibjson.year:[{filtri.anno_da or 1800} TO {filtri.anno_a or 3000}]"

    async def search(self, client: httpx.AsyncClient, query: str, limit: int, config: Config, filtri=None):
        url = f"{API}/{quote(query, safe='')}"
        response = await client.get(url, params={"pageSize": str(min(limit, 100))}, timeout=25)
        response.raise_for_status()
        return [_work(item.get("bibjson", {})) for item in response.json().get("results", [])]


def _work(bib: dict) -> Work:
    doi = None
    for identifier in bib.get("identifier", []):
        if identifier.get("type") == "doi":
            doi = identifier.get("id")
    link = next((l.get("url") for l in bib.get("link", []) if l.get("url")), None)
    year = bib.get("year")
    return Work(
        title=clean(bib.get("title")) or "(senza titolo)",
        authors=[a["name"] for a in bib.get("author", []) if a.get("name")],
        year=int(year) if str(year).isdigit() else None,
        doi=clean(doi),
        venue=clean((bib.get("journal") or {}).get("title")),
        url=clean(link) or (f"https://doi.org/{doi}" if doi else None),
        abstract=clean(bib.get("abstract")),
        oa_url=clean(link),
        sources=["doaj"],
    )
