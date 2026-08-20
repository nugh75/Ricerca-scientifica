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
    "doi": "https://doi.org/10.1000/citante",
    "abstract_inverted_index": {"Abstract": [0], "consultabile": [1]},
    "best_oa_location": {"pdf_url": "https://example.org/citante.pdf"},
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
def test_ogni_lavoro_collegato_si_seleziona_dall_inizio_e_si_puo_leggere():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    id_ricerca = ricerca_salvata()
    pagina = client.get(f"/citazioni/{id_ricerca}/0/avanti").text

    assert pagina.index('name="scelti"') < pagina.index("Chi mi cita")
    assert "citazione-record" in pagina
    assert "<details" in pagina and "Abstract consultabile" in pagina
    assert "https://example.org/citante.pdf" in pagina
    assert "https://doi.org/10.1000/citante" in pagina


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


@respx.mock
def test_un_record_non_openalex_viene_risolto_dal_doi():
    id_ricerca = history.salva(
        "topic", Strategy(blocks=[Block("B", ["x"])]),
        [SourceResult("crossref", "Crossref", "q")],
        [Work(title="Da Crossref", doi="10.1000/seme", sources=["crossref"])],
    )
    respx.get(
        url__startswith="https://api.openalex.org/works/https://doi.org/10.1000/seme"
    ).mock(return_value=httpx.Response(200, json={
        "id": "https://openalex.org/W1", "title": "Da Crossref",
        "doi": "https://doi.org/10.1000/seme",
        "authorships": [], "primary_location": {},
    }))
    respx.get(url__startswith="https://api.openalex.org/works?").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    pagina = client.get(f"/citazioni/{id_ricerca}/0/avanti")
    assert pagina.status_code == 200
    assert "Chi mi cita" in pagina.text
    assert "non viene da OpenAlex" not in pagina.text
