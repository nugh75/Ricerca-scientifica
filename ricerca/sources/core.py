from __future__ import annotations

import httpx

from ..config import Config
from ..models import Work
from .base import Source, clean, testo

API = "https://api.core.ac.uk/v3/search/works"


class Core(Source):
    id = "core"
    label = "CORE"
    homepage = "https://core.ac.uk"
    key_field = "core_api_key"
    key_hint_key = "need_core_key"

    async def search(self, client: httpx.AsyncClient, query: str, limit: int, config: Config, filtri=None):
        response = await client.get(
            API,
            params={"q": query, "limit": str(min(limit, 50))},
            headers={"Authorization": f"Bearer {config.core_api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        return [_work(item) for item in response.json().get("results", [])]


def _work(item: dict) -> Work:
    year = item.get("yearPublished")
    authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
    return Work(
        title=clean(item.get("title")) or "(senza titolo)",
        authors=authors,
        year=int(year) if str(year).isdigit() else None,
        doi=clean(item.get("doi")),
        venue=clean(item.get("publisher")),
        url=clean(item.get("doi") and f"https://doi.org/{item['doi']}") or clean(item.get("id")),
        abstract=testo(item.get("abstract")),
        oa_url=clean(item.get("downloadUrl")),
        sources=["core"],
    )
