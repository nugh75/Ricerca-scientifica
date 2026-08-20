import httpx
import respx

from ricerca import sources
from ricerca.config import Config

RISPOSTA = {"meta": {"cost_usd": 0.001}, "results": [{
    "id": "https://openalex.org/W42",
    "title": "Un articolo ritirato",
    "publication_year": 2024,
    "authorships": [{"author": {
        "id": "https://openalex.org/A123", "display_name": "Ada Rossi",
    }}],
    "primary_location": {"source": {
        "id": "https://openalex.org/S456", "display_name": "Journal of Tests",
        "type": "journal",
    }},
    "abstract_inverted_index": {"Un": [0], "abstract": [1], "vero": [2]},
    "is_retracted": True,
    "cited_by_count": 137,
    "citation_normalized_percentile": {"is_in_top_10_percent": True},
    "has_content": {"pdf": True},
    "content_urls": {"pdf": "https://content.openalex.org/works/W42.pdf"},
}]}


@respx.mock
async def test_il_record_porta_i_campi_nuovi():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["openalex"].search(client, "q", 5, Config())
    work = works[0]
    assert work.openalex_id == "W42"
    assert work.abstract == "Un abstract vero"
    assert work.ritirato is True
    assert work.citazioni == 137
    assert work.molto_citato is True
    assert work.pdf_archivio == "https://content.openalex.org/works/W42.pdf"
    assert work.author_ids == ["A123"]
    assert work.venue_id == "S456"


@respx.mock
async def test_un_record_senza_i_campi_nuovi_non_esplode():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"meta": {}, "results": [{
            "id": "https://openalex.org/W1", "title": "Scarno",
            "authorships": [], "primary_location": {},
        }]})
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["openalex"].search(client, "q", 5, Config())
    assert works[0].abstract is None
    assert works[0].ritirato is False
    assert works[0].citazioni is None
    assert works[0].pdf_archivio == ""
