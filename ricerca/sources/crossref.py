from __future__ import annotations

import httpx

from ..config import Config
from ..models import Strategy, Work
from ..strategy import flat_terms
from .base import Source, clean, testo

API = "https://api.crossref.org/works"


class Crossref(Source):
    id = "crossref"
    label = "Crossref"
    homepage = "https://www.crossref.org"

    def render_query(self, strategy: Strategy) -> str:
        # L'indice di Crossref non interpreta gli operatori booleani.
        return flat_terms(strategy)

    async def search(self, client: httpx.AsyncClient, query: str, limit: int, config: Config, filtri=None):
        params = {"query.bibliographic": query, "rows": str(min(limit, 100))}
        if config.mailto_valido:
            params["mailto"] = config.mailto_valido
        vincoli = []
        if filtri and filtri.anno_da:
            vincoli.append(f"from-pub-date:{filtri.anno_da}-01-01")
        if filtri and filtri.anno_a:
            vincoli.append(f"until-pub-date:{filtri.anno_a}-12-31")
        if filtri and filtri.solo_articoli:
            vincoli.append("type:journal-article")
        if vincoli:
            params["filter"] = ",".join(vincoli)

        response = await client.get(API, params=params, timeout=25)
        response.raise_for_status()
        return [_work(item) for item in response.json().get("message", {}).get("items", [])]


def _work(item: dict) -> Work:
    titoli = item.get("title") or []
    sede = item.get("container-title") or []
    parti = (item.get("issued") or {}).get("date-parts") or [[]]
    anno = parti[0][0] if parti and parti[0] else None
    autori = []
    for autore in item.get("author", []):
        nome = " ".join(p for p in (autore.get("given"), autore.get("family")) if p)
        if nome:
            autori.append(nome)
    abstract = item.get("abstract")
    return Work(
        title=clean(titoli[0] if titoli else None) or "(senza titolo)",
        authors=autori,
        year=int(anno) if str(anno).isdigit() else None,
        doi=clean(item.get("DOI")),
        venue=clean(sede[0] if sede else None),
        url=clean(item.get("URL")),
        abstract=testo(abstract),
        sources=["crossref"],
    )
