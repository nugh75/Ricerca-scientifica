import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import openalex_api
from ricerca.app import app
from ricerca.config import Config

RISPOSTA = {"meta": {"cost_usd": 0.0}, "results": [
    {"id": "https://openalex.org/S9692511", "display_name": "Frontiers in Psychology",
     "hint": "Frontiers Media", "entity_type": "source"},
]}


@respx.mock
async def test_l_autocomplete_restituisce_id_e_nome():
    respx.get(url__startswith="https://api.openalex.org/autocomplete/sources").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        voci = await openalex_api.autocompleta("sources", "front", Config(), client)
    assert voci[0]["id"] == "S9692511"
    assert voci[0]["nome"] == "Frontiers in Psychology"
    assert voci[0]["nota"] == "Frontiers Media"


@respx.mock
async def test_un_entita_non_prevista_non_parte():
    rotta = respx.get(url__startswith="https://api.openalex.org/autocomplete").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        voci = await openalex_api.autocompleta("../segreti", "x", Config(), client)
    assert voci == []
    assert not rotta.called


@respx.mock
async def test_una_domanda_troppo_corta_non_parte():
    rotta = respx.get(url__startswith="https://api.openalex.org/autocomplete").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        assert await openalex_api.autocompleta("sources", "f", Config(), client) == []
    assert not rotta.called


@respx.mock
def test_la_rotta_rende_le_opzioni():
    respx.get(url__startswith="https://api.openalex.org/autocomplete/keywords").mock(
        return_value=httpx.Response(200, json={"meta": {}, "results": [
            {"id": "https://openalex.org/keywords/ai-literacy",
             "display_name": "AI literacy", "hint": ""},
        ]})
    )
    pagina = TestClient(app).get("/autocompleta", params={"entita": "keywords", "q": "ai li"})
    assert pagina.status_code == 200
    assert "AI literacy" in pagina.text
    assert 'value="AI literacy"' in pagina.text


@respx.mock
def test_i_suggerimenti_per_i_blocchi_sono_pulsanti_visibili():
    respx.get(url__startswith="https://api.openalex.org/autocomplete/keywords").mock(
        return_value=httpx.Response(200, json={"meta": {}, "results": [
            {"id": "https://openalex.org/keywords/ai-literacy",
             "display_name": "AI literacy", "hint": "Keyword"},
        ]})
    )
    pagina = TestClient(app).get(
        "/autocompleta", params={"entita": "keywords", "q": "ai li", "modo": "pulsanti"}
    )
    assert 'type="button"' in pagina.text
    assert 'data-termine="AI literacy"' in pagina.text


@respx.mock
def test_se_openalex_e_giu_la_rotta_risponde_vuota():
    respx.get(url__startswith="https://api.openalex.org/autocomplete").mock(
        return_value=httpx.Response(500)
    )
    pagina = TestClient(app).get("/autocompleta", params={"entita": "keywords", "q": "ai li"})
    assert pagina.status_code == 200
    assert pagina.text.strip() == ""
