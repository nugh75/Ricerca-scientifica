from __future__ import annotations

from xml.etree import ElementTree

import httpx

from ..config import Config
from ..models import Strategy, Work
from ..strategy import or_group
from .base import Source, clean, testo

API = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"


class Arxiv(Source):
    id = "arxiv"
    label = "arXiv"
    homepage = "https://arxiv.org"

    def render_query(self, strategy: Strategy) -> str:
        groups = [or_group(b.clean_terms(), 'all:"{term}"') for b in strategy.non_empty_blocks()]
        if not groups:
            return ""
        return " AND ".join(f"({g})" for g in groups) + self.render_filtri(strategy)

    def render_filtri(self, strategy: Strategy) -> str:
        filtri = strategy.filtri
        if not (filtri.anno_da or filtri.anno_a):
            return ""
        da = f"{filtri.anno_da or 1800}0101"
        a = f"{filtri.anno_a or 2999}1231"
        return f" AND submittedDate:[{da} TO {a}]"

    async def search(self, client: httpx.AsyncClient, query: str, limit: int, config: Config, filtri=None):
        params = {"search_query": query, "max_results": str(min(limit, 50))}
        response = await client.get(API, params=params, timeout=30)
        response.raise_for_status()
        root = ElementTree.fromstring(response.text)
        return [_work(entry) for entry in root.findall(f"{ATOM}entry")]


def _work(entry) -> Work:
    published = (entry.findtext(f"{ATOM}published") or "")[:4]
    doi = entry.findtext("{http://arxiv.org/schemas/atom}doi")
    link = entry.findtext(f"{ATOM}id")
    pdf = None
    for node in entry.findall(f"{ATOM}link"):
        if node.get("title") == "pdf":
            pdf = node.get("href")
    return Work(
        title=" ".join((entry.findtext(f"{ATOM}title") or "").split()) or "(senza titolo)",
        authors=[
            (a.findtext(f"{ATOM}name") or "").strip()
            for a in entry.findall(f"{ATOM}author")
            if a.findtext(f"{ATOM}name")
        ],
        year=int(published) if published.isdigit() else None,
        doi=clean(doi),
        venue="arXiv",
        url=clean(link),
        abstract=testo(entry.findtext(f"{ATOM}summary")),
        oa_url=clean(pdf),
        sources=["arxiv"],
    )
