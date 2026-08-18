import httpx
import respx

from ricerca import keywords, search
from ricerca.config import Config
from ricerca.models import Block, Strategy

BUDGET = {
    "error": "Rate limit exceeded",
    "message": "Insufficient budget. This request costs $0.01 but you only have $0.0006 remaining.",
}
WORKS = {"results": [{"title": "AI literacy", "keywords": [{"display_name": "Literacy"}]}]}


def test_email_malformata_non_viene_spedita():
    assert Config(mailto="nome esempio.it").mailto_valido == ""
    assert Config(mailto="nome@esempio.it").mailto_valido == "nome@esempio.it"


@respx.mock
async def test_openalex_riceve_l_email_solo_se_valida():
    rotta = respx.get(url__startswith=f"{keywords.OPENALEX}/works").mock(
        return_value=httpx.Response(200, json=WORKS)
    )
    async with httpx.AsyncClient() as client:
        await keywords._openalex("x", client, Config(mailto="rotta @ mail"))
        await keywords._openalex("x", client, Config(mailto="ok@esempio.it"))

    assert "mailto" not in str(rotta.calls[0].request.url)
    assert "mailto=ok%40esempio.it" in str(rotta.calls[1].request.url)


def test_il_messaggio_dell_api_viene_estratto():
    assert "Insufficient budget" in keywords.messaggio_api(httpx.Response(429, json=BUDGET))


def test_un_errore_di_testo_semplice_viene_riportato():
    assert keywords.messaggio_api(httpx.Response(400, text="Invalid mailto")) == "Invalid mailto"


def test_una_pagina_html_non_finisce_nella_nota():
    assert keywords.messaggio_api(httpx.Response(400, text="<html>errore</html>")) == ""


@respx.mock
async def test_la_nota_dei_suggerimenti_riporta_la_spiegazione_di_openalex():
    respx.get(url__startswith=f"{keywords.OPENALEX}/works").mock(
        return_value=httpx.Response(429, json=BUDGET)
    )
    respx.get(url__startswith=f"{keywords.EUTILS}/esearch.fcgi").mock(
        return_value=httpx.Response(200, json={"esearchresult": {}})
    )
    async with httpx.AsyncClient() as client:
        risultato = await keywords.gather("AI literacy", client, Config())

    assert any("Insufficient budget" in nota for nota in risultato.notes)


@respx.mock
async def test_un_400_senza_json_dice_comunque_qualcosa():
    respx.get(url__startswith=f"{keywords.OPENALEX}/works").mock(
        return_value=httpx.Response(400, text="Invalid query parameter: title")
    )
    respx.get(url__startswith=f"{keywords.EUTILS}/esearch.fcgi").mock(
        return_value=httpx.Response(200, json={"esearchresult": {}})
    )
    async with httpx.AsyncClient() as client:
        risultato = await keywords.gather("x", client, Config())

    assert any("Invalid query parameter" in nota for nota in risultato.notes)


@respx.mock
async def test_l_errore_di_una_fonte_riporta_la_spiegazione():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(400, json={"message": "Invalid mailto parameter"})
    )
    risultati, _ = await search.run(
        Strategy([Block("C", ["x"])]), ["openalex"], 5, Config()
    )
    assert risultati[0].error == "HTTP 400 — Invalid mailto parameter"
