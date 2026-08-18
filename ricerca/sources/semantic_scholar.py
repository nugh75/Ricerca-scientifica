from __future__ import annotations

import httpx

from ..config import Config
from ..i18n import strings
from ..models import Strategy, Work
from ..strategy import flat_terms
from .base import Source, clean

API = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,year,abstract,venue,externalIds,openAccessPdf,authors,url"


class SemanticScholar(Source):
    id = "semanticscholar"
    label = "Semantic Scholar"
    homepage = "https://www.semanticscholar.org"

    def render_query(self, strategy: Strategy) -> str:
        # L'endpoint di ricerca non interpreta gli operatori booleani.
        return flat_terms(strategy)

    async def search(self, client: httpx.AsyncClient, query: str, limit: int, config: Config, filtri=None):
        headers = {"x-api-key": config.s2_api_key} if config.s2_api_key else {}
        params = {"query": query, "limit": str(min(limit, 100)), "fields": FIELDS}
        if filtri and (filtri.anno_da or filtri.anno_a):
            params["year"] = f"{filtri.anno_da or ''}-{filtri.anno_a or ''}"
        response = await client.get(
            API,
            params=params,
            headers=headers,
            timeout=30,
        )
        if response.status_code == 429:
            raise RuntimeError(strings(config.lang)["s2_hint"])
        response.raise_for_status()
        return [_work(item) for item in response.json().get("data", [])]


def _work(item: dict) -> Work:
    external = item.get("externalIds") or {}
    pdf = (item.get("openAccessPdf") or {}).get("url")
    return Work(
        title=clean(item.get("title")) or "(senza titolo)",
        authors=[a["name"] for a in item.get("authors", []) if a.get("name")],
        year=item.get("year"),
        doi=clean(external.get("DOI")),
        venue=clean(item.get("venue")),
        url=clean(item.get("url")),
        abstract=clean(item.get("abstract")),
        oa_url=clean(pdf),
        sources=["semanticscholar"],
    )
