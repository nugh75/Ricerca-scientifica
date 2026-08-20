from __future__ import annotations

import httpx

from .. import openalex_api
from ..config import Config
from ..i18n import strings
from ..models import Work
from .base import Source, clean

# Tutto quello che serve al programma, in una sola chiamata: l'abstract, lo
# stato di ritiro, le citazioni e la copia nell'archivio non costano di più.
SELECT = (
    "id,doi,title,publication_year,authorships,primary_location,best_oa_location,"
    "open_access,locations,abstract_inverted_index,is_retracted,cited_by_count,"
    "citation_normalized_percentile,has_content,content_urls,language"
)


class OpenAlex(Source):
    id = "openalex"
    label = "OpenAlex"
    homepage = "https://openalex.org"

    def avviso(self, config: Config, lang: str | None = None) -> str | None:
        # Senza chiave si finisce nella corsia anonima, limitata e a budget.
        return None if config.openalex_api_key else strings(lang)["openalex_budget"]

    async def search(self, client: httpx.AsyncClient, query: str, limit: int, config: Config, filtri=None):
        corpo = await openalex_api.chiama(
            client,
            "/works",
            config,
            filter=filtro(query, filtri),
            per_page=str(min(limit, 50)),
            select=SELECT,
        )
        return [work_da(item) for item in corpo.get("results", [])]


def filtro_testo(query: str) -> str:
    """La parte della domanda che cerca parole nel testo."""

    return f"title_and_abstract.search:{query}"


def filtro_vincoli(filtri=None) -> list[str]:
    """I vincoli che valgono a prescindere dalla domanda, uno per elemento."""

    pezzi = []
    if filtri and filtri.anno_da:
        pezzi.append(f"from_publication_date:{filtri.anno_da}-01-01")
    if filtri and filtri.anno_a:
        pezzi.append(f"to_publication_date:{filtri.anno_a}-12-31")
    if filtri and filtri.solo_articoli:
        pezzi.append("type:article")
    if filtri and filtri.lingua:
        pezzi.append(f"language:{filtri.lingua}")
    if filtri and filtri.escludi_ritirati:
        pezzi.append("is_retracted:false")
    if filtri and filtri.solo_oa:
        pezzi.append("is_oa:true")
    if filtri and filtri.con_pdf:
        pezzi.append("has_content.pdf:true")
    return pezzi


def filtro(query: str, filtri=None) -> str:
    """I due pezzi uniti nella sintassi di OpenAlex."""

    return ",".join([filtro_testo(query), *filtro_vincoli(filtri)])


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


def work_da(item: dict) -> Work:
    location = item.get("primary_location") or {}
    venue = (location.get("source") or {}).get("display_name")
    candidati = _pdf_candidati(item)
    percentile = item.get("citation_normalized_percentile") or {}
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
        abstract=openalex_api.abstract_da_indice(item.get("abstract_inverted_index")),
        oa_url=candidati[0] if candidati else None,
        oa_urls=candidati[1:],
        sources=["openalex"],
        openalex_id=openalex_api.id_breve(item.get("id")),
        ritirato=bool(item.get("is_retracted")),
        citazioni=item.get("cited_by_count"),
        molto_citato=bool(percentile.get("is_in_top_10_percent")),
        pdf_archivio=str((item.get("content_urls") or {}).get("pdf") or ""),
    )
