from __future__ import annotations

import httpx

from ..config import Config
from ..models import Strategy, Work
from ..strategy import or_group
from .base import Source, clean

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMed(Source):
    id = "pubmed"
    label = "PubMed"
    homepage = "https://pubmed.ncbi.nlm.nih.gov"

    def render_query(self, strategy: Strategy) -> str:
        groups = [
            or_group(b.clean_terms(), '"{term}"[tiab]') for b in strategy.non_empty_blocks()
        ]
        if strategy.mesh:
            groups.append(or_group(strategy.mesh, '"{term}"[MeSH Terms]'))
        if not groups:
            return ""
        return " AND ".join(f"({g})" for g in groups) + self.render_filtri(strategy)

    def render_filtri(self, strategy: Strategy) -> str:
        filtri, coda = strategy.filtri, ""
        if filtri.anno_da or filtri.anno_a:
            da = filtri.anno_da or 1800
            a = filtri.anno_a or 3000
            coda += f' AND ("{da}"[dp] : "{a}"[dp])'
        if filtri.solo_articoli:
            coda += ' AND ("journal article"[pt])'
        return coda

    async def search(self, client: httpx.AsyncClient, query: str, limit: int, config: Config, filtri=None):
        params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": str(limit)}
        if config.ncbi_api_key:
            params["api_key"] = config.ncbi_api_key
        response = await client.get(f"{EUTILS}/esearch.fcgi", params=params, timeout=25)
        response.raise_for_status()
        ids = response.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
        if config.ncbi_api_key:
            params["api_key"] = config.ncbi_api_key
        response = await client.get(f"{EUTILS}/esummary.fcgi", params=params, timeout=25)
        response.raise_for_status()
        result = response.json().get("result", {})
        return [_work(result[pmid]) for pmid in result.get("uids", []) if pmid in result]


def _work(item: dict) -> Work:
    doi = pmcid = None
    for identifier in item.get("articleids", []):
        if identifier.get("idtype") == "doi":
            doi = identifier.get("value")
        elif identifier.get("idtype") == "pmc":
            pmcid = identifier.get("value")
    pmid = item.get("uid", "")
    year = None
    pubdate = str(item.get("pubdate", ""))[:4]
    if pubdate.isdigit():
        year = int(pubdate)
    return Work(
        title=clean(item.get("title")) or "(senza titolo)",
        authors=[a["name"] for a in item.get("authors", []) if a.get("name")],
        year=year,
        doi=clean(doi),
        venue=clean(item.get("source")),
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
        # La copia in PubMed Central è aperta per definizione.
        oa_url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/" if pmcid else None,
        sources=["pubmed"],
    )
