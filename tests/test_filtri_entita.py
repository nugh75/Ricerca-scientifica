import httpx
import respx
from fastapi.testclient import TestClient

from ricerca.app import app
from ricerca.models import Filtri
from ricerca.sources.openalex import filtro
from ricerca.strategy import identificativo, strategy_from_form


def test_gli_identificativi_entrano_nel_filtro():
    reso = filtro("x", Filtri(
        rivista_id="S9692511", ateneo_id="I27837315", finanziatore_id="F4320306076"
    ))
    assert "primary_location.source.id:S9692511" in reso
    assert "authorships.institutions.id:I27837315" in reso
    assert "funders.id:F4320306076" in reso


def test_un_nome_scritto_a_mano_non_diventa_un_filtro():
    assert identificativo("Frontiers in Psychology", "S") == ""
    assert identificativo("S9692511", "S") == "S9692511"
    assert identificativo("s9692511", "S") == "S9692511"
    assert identificativo("I123", "S") == ""
    assert identificativo("", "S") == ""


def test_il_modulo_scarta_quello_che_non_e_un_identificativo():
    strategy = strategy_from_form(
        ["B"], ["ai"], rivista="Frontiers in Psychology", ateneo="I27837315",
        finanziatore="",
    )
    assert strategy.filtri.rivista_id == ""
    assert strategy.filtri.ateneo_id == "I27837315"


@respx.mock
def test_gli_identificativi_arrivano_dal_modulo_reale(esegui_ricerca):
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    esegui_ricerca(TestClient(app), {
        "label": ["B"], "terms": ["ai"], "fonte": ["openalex"],
        "rivista": "S9692511", "ateneo": "I27837315",
        "finanziatore": "F4320306076",
    })
    indirizzo = str(rotta.calls[0].request.url)
    assert "primary_location.source.id%3AS9692511" in indirizzo
    assert "authorships.institutions.id%3AI27837315" in indirizzo
    assert "funders.id%3AF4320306076" in indirizzo
