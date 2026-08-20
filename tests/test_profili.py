import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import profili
from ricerca.app import app
from ricerca.config import Config


client = TestClient(app)

AUTORE = {
    "id": "https://openalex.org/A123",
    "display_name": "Ada Rossi",
    "orcid": "https://orcid.org/0000-0001-2345-6789",
    "works_count": 42,
    "cited_by_count": 1234,
    "summary_stats": {"h_index": 17, "i10_index": 21, "2yr_mean_citedness": 3.4},
    "last_known_institutions": [{"display_name": "Università di Prova"}],
    "counts_by_year": [{"year": 2024, "works_count": 4, "cited_by_count": 20}],
}

RIVISTA = {
    "id": "https://openalex.org/S456",
    "display_name": "Journal of Tests",
    "type": "journal",
    "issn_l": "1234-5678",
    "works_count": 800,
    "cited_by_count": 9000,
    "summary_stats": {"h_index": 55, "i10_index": 400, "2yr_mean_citedness": 2.7},
    "host_organization_name": "Test Press",
    "is_oa": True,
    "is_in_doaj": True,
    "homepage_url": "https://journal.example",
    "counts_by_year": [{"year": 2024, "works_count": 50, "cited_by_count": 300}],
}

LAVORO = {
    "id": "https://openalex.org/W9",
    "title": "Il lavoro più citato",
    "publication_year": 2024,
    "authorships": [],
    "primary_location": {},
    "cited_by_count": 99,
}


def test_i_parser_tengono_metriche_e_identita():
    autore = profili.da_autore(AUTORE)
    rivista = profili.da_rivista(RIVISTA)

    assert autore["id"] == "A123"
    assert autore["istituzione"] == "Università di Prova"
    assert autore["h_index"] == 17
    assert autore["anni"][0]["citazioni"] == 20
    assert rivista["id"] == "S456"
    assert rivista["editore"] == "Test Press"
    assert rivista["doaj"] is True


@respx.mock
async def test_la_ricerca_delle_riviste_esclude_le_altre_sedi():
    rotta = respx.get(url__startswith="https://api.openalex.org/sources").mock(
        return_value=httpx.Response(200, json={"meta": {}, "results": [RIVISTA]})
    )
    async with httpx.AsyncClient() as http:
        risultati = await profili.cerca("riviste", "tests", Config(), http)

    assert risultati[0]["nome"] == "Journal of Tests"
    assert "type%3Ajournal" in str(rotta.calls[0].request.url)


@respx.mock
def test_la_pagina_autore_mostra_metriche_e_lavori():
    respx.get("https://api.openalex.org/authors/A123").mock(
        return_value=httpx.Response(200, json=AUTORE)
    )
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"meta": {}, "results": [LAVORO]})
    )

    pagina = client.get("/autori/A123").text

    assert "Ada Rossi" in pagina
    assert "1,234" in pagina
    assert "17" in pagina
    assert "Il lavoro più citato" in pagina


def test_un_identificativo_di_profilo_inventato_non_diventa_un_endpoint():
    assert profili.identificativo("../../works", "A") == ""
