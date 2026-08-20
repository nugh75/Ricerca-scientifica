import httpx
import respx

from ricerca import faccette
from ricerca.config import Config
from ricerca.models import Filtri


def gruppi(*coppie):
    return {"meta": {"cost_usd": 0.0001}, "group_by": [
        {"key": str(k), "key_display_name": str(k), "count": n} for k, n in coppie
    ]}


@respx.mock
async def test_il_profilo_raccoglie_tutti_i_campi():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=gruppi(("2024", 40), ("2023", 10)))
    )
    async with httpx.AsyncClient() as client:
        profilo = await faccette.profilo("ai literacy", Filtri(), Config(), client)
    assert len(profilo) == len(faccette.CAMPI)
    primo = profilo[0]
    assert primo["campo"] == faccette.CAMPI[0][0]
    assert primo["voci"][0]["etichetta"] == "2024"
    assert primo["voci"][0]["quota"] == 100
    assert primo["voci"][1]["quota"] == 25


@respx.mock
async def test_un_campo_che_fallisce_non_ferma_gli_altri():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        side_effect=[
            httpx.Response(500),
            *[httpx.Response(200, json=gruppi(("x", 1)))] * (len(faccette.CAMPI) - 1),
        ]
    )
    async with httpx.AsyncClient() as client:
        profilo = await faccette.profilo("ai literacy", Filtri(), Config(), client)
    assert profilo[0]["voci"] == []
    assert profilo[1]["voci"]


@respx.mock
async def test_i_filtri_valgono_anche_per_le_faccette():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=gruppi(("x", 1)))
    )
    async with httpx.AsyncClient() as client:
        await faccette.profilo("ai", Filtri(escludi_ritirati=True), Config(), client)
    assert "is_retracted%3Afalse" in str(rotta.calls[0].request.url)


@respx.mock
def test_la_rotta_disegna_le_barre():
    from fastapi.testclient import TestClient
    from ricerca import history
    from ricerca.app import app
    from ricerca.models import Block, SourceResult, Strategy, Work

    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=gruppi(("2024", 40)))
    )
    id_ricerca = history.salva(
        "topic", Strategy(blocks=[Block("B", ["x"])]),
        [SourceResult("openalex", "OpenAlex", "title_and_abstract.search:x")],
        [Work(title="Uno")],
    )
    pagina = TestClient(app).get(f"/faccette/{id_ricerca}")
    assert pagina.status_code == 200
    assert "2024" in pagina.text


def test_una_voce_di_cronologia_senza_filtri_non_rompe_nulla():
    from ricerca import history

    assert history.filtri("id-che-non-esiste") == Filtri()
