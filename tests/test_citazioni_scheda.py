import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import history
from ricerca.app import app
from ricerca.models import Block, SourceResult, Strategy, Work

client = TestClient(app)


def ricerca_salvata() -> str:
    return history.salva(
        "topic",
        Strategy(blocks=[Block("B", ["x"])]),
        [SourceResult("openalex", "OpenAlex", "q")],
        [Work(title="Il seme", openalex_id="W1", sources=["openalex"])],
    )


RISPOSTA = {"meta": {"cost_usd": 0.0001}, "results": [{
    "id": "https://openalex.org/W9", "title": "Chi mi cita",
    "publication_year": 2025, "authorships": [], "primary_location": {},
}]}


@respx.mock
def test_la_scheda_elenca_chi_cita():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    id_ricerca = ricerca_salvata()
    pagina = client.get(f"/citazioni/{id_ricerca}/0/avanti")
    assert pagina.status_code == 200
    assert "Chi mi cita" in pagina.text


@respx.mock
def test_i_record_scelti_entrano_nella_ricerca():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    id_ricerca = ricerca_salvata()
    risposta = client.post(f"/citazioni/{id_ricerca}/0/avanti", data={"scelti": ["W9"]})
    assert risposta.status_code == 200
    titoli = [w.title for w in history.record(id_ricerca)]
    assert titoli == ["Il seme", "Chi mi cita"]


def test_un_record_senza_identificativo_spiega_invece_di_rompersi():
    id_ricerca = history.salva(
        "topic", Strategy(blocks=[Block("B", ["x"])]),
        [SourceResult("crossref", "Crossref", "q")],
        [Work(title="Da Crossref", sources=["crossref"])],
    )
    pagina = client.get(f"/citazioni/{id_ricerca}/0/avanti")
    assert pagina.status_code == 200
    assert "OpenAlex" in pagina.text
