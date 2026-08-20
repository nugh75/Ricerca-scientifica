import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import history, sources
from ricerca.app import app
from ricerca.config import Config
from ricerca.models import Filtri


def pagina(ids, cursore=None):
    return {
        "meta": {"cost_usd": 0.0001, "next_cursor": cursore},
        "results": [
            {"id": f"https://openalex.org/{i}", "title": str(i),
             "authorships": [], "primary_location": {}} for i in ids
        ],
    }


@respx.mock
async def test_oltre_cento_record_si_pagina_col_cursore():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        side_effect=[
            httpx.Response(200, json=pagina([f"W{n}" for n in range(100)], "IlsxMDAu")),
            httpx.Response(200, json=pagina([f"X{n}" for n in range(50)], None)),
        ]
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["openalex"].search(client, "q", 150, Config())
    assert len(works) == 150


@respx.mock
async def test_il_cursore_si_ferma_al_tetto():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(
            200, json=pagina([f"W{n}" for n in range(100)], "ancora")
        )
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["openalex"].search(client, "q", 999, Config())
    assert len(works) <= 200


@respx.mock
async def test_il_campione_e_una_chiamata_sola_con_il_seme():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=pagina(["W1", "W2"], "ancora"))
    )
    async with httpx.AsyncClient() as client:
        await sources.BY_ID["openalex"].search(
            client, "q", 150, Config(), Filtri(campione=20, seme=7)
        )
    assert len(rotta.calls) == 1
    indirizzo = str(rotta.calls[0].request.url)
    assert "sample=20" in indirizzo
    assert "seed=7" in indirizzo
    assert "cursor" not in indirizzo


def test_il_modulo_legge_campione_e_seme():
    from ricerca.strategy import strategy_from_form

    filtri = strategy_from_form(["B"], ["ai"], campione="50", seme="7").filtri
    assert filtri.campione == 50
    assert filtri.seme == 7
    vuoti = strategy_from_form(["B"], ["ai"], campione="", seme="x").filtri
    assert vuoti.campione is None
    assert vuoti.seme is None
    assert strategy_from_form(["B"], ["ai"], campione="101").filtri.campione is None


def test_il_protocollo_mette_in_evidenza_campione_e_seme():
    from ricerca.export import protocollo, protocollo_testo

    voce = {"topic": "x", "quando": "2026-08-20", "blocchi": [], "fonti": [],
            "filtri": {"campione": 50, "seme": 7}}
    assert "Campione casuale: 50 record, seme 7" in protocollo(voce, {})
    assert "Campione casuale: 50 record, seme 7" in protocollo_testo(voce, {})


@respx.mock
def test_la_rotta_permette_di_chiedere_centocinquanta_record(esegui_ricerca):
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        side_effect=[
            httpx.Response(200, json=pagina([f"W{n}" for n in range(100)], "dopo")),
            httpx.Response(200, json=pagina([f"X{n}" for n in range(50)])),
        ]
    )
    esegui_ricerca(TestClient(app), {
        "label": ["B"], "terms": ["ai"], "fonte": ["openalex"], "limite": "150",
    })
    assert history.elenco()[0]["totale"] == 150
