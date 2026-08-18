import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import config as config_module
from ricerca.app import app
from ricerca.config import Config

client = TestClient(app)

CONCEPTS = {"concepts": [{"display_name": "Literacy", "score": 0.6}]}
TOPICS = {"topics": [{"display_name": "Online Learning"}]}
MESH = {"esearchresult": {"translationset": [{"from": "l", "to": '"literacy"[MeSH Terms]'}]}}
WORKS_TITLES = {"results": [{"title": "AI literacy in higher education"}, {"title": "higher education AI"}]}
WORKS_FULL = {"results": [{"id": "https://openalex.org/W1", "title": "Uno", "publication_year": 2024,
                           "doi": "https://doi.org/10.1/x", "authorships": [{"author": {"display_name": "A. Rossi"}}],
                           "primary_location": {"source": {"display_name": "Rivista"}}}]}


def test_home_mostra_il_form():
    page = client.get("/")
    assert page.status_code == 200
    assert "Suggerisci le parole chiave" in page.text
    assert "Nessun LLM configurato" in page.text


@respx.mock
def test_suggerimenti_costruisce_i_blocchi_senza_llm():
    respx.get(url__startswith="https://api.openalex.org/text/concepts").mock(return_value=httpx.Response(200, json=CONCEPTS))
    respx.get(url__startswith="https://api.openalex.org/text/topics").mock(return_value=httpx.Response(200, json=TOPICS))
    respx.get(url__startswith="https://api.openalex.org/works").mock(return_value=httpx.Response(200, json=WORKS_TITLES))
    respx.get(url__startswith="https://eutils.ncbi.nlm.nih.gov").mock(return_value=httpx.Response(200, json=MESH))

    page = client.post("/suggerimenti", data={"topic": "AI literacy"})

    assert page.status_code == 200
    assert "Literacy" in page.text
    assert "higher education" in page.text
    assert "blocchi costruiti dai soli dati" in page.text
    assert "nessuna ricerca è ancora partita" in page.text  # il passo 2 non cerca da solo
    assert "TITLE-ABS-KEY(" in page.text  # la stringa Scopus e' gia' pronta


def test_query_rende_le_stringhe_per_ogni_motore():
    page = client.post("/query", data={"label": ["Concetto"], "terms": ["AI literacy, AI competence"], "mesh": ""})
    assert '(&#34;AI literacy&#34; OR &#34;AI competence&#34;)' in page.text
    assert "tiab" in page.text


@respx.mock
def test_cerca_mostra_risultati_ed_export():
    respx.get(url__startswith="https://api.openalex.org/works").mock(return_value=httpx.Response(200, json=WORKS_FULL))
    respx.get(url__startswith="https://doaj.org").mock(return_value=httpx.Response(500))

    page = client.post("/cerca", data={
        "label": ["Concetto"], "terms": ["AI literacy"], "mesh": "",
        "fonte": ["openalex", "doaj"], "limite": "5",
    })

    assert "Uno" in page.text
    assert "HTTP 500" in page.text
    token = page.text.split("/export/")[1].split(".bib")[0]

    bib = client.get(f"/export/{token}.bib")
    assert "@article{" in bib.text
    csv = client.get(f"/export/{token}.csv")
    assert csv.text.startswith("titolo,autori,anno")


def test_impostazioni_salva_su_file(isolated_config):
    risposta = client.post("/impostazioni", data={
        "mailto": "x@y.it", "llm_base_url": "http://localhost:11434/v1", "llm_model": "qwen3:8b",
        "llm_api_key": "", "core_api_key": "", "s2_api_key": "", "ncbi_api_key": "",
    }, follow_redirects=True)
    assert risposta.status_code == 200
    assert config_module.load().llm_model == "qwen3:8b"
    assert "salvato in" in risposta.text


@respx.mock
def test_elenco_modelli_riporta_errore_leggibile():
    respx.get("http://spento/v1/models").mock(side_effect=httpx.ConnectError("connessione rifiutata"))
    page = client.post("/impostazioni/modelli", data={"llm_base_url": "http://spento/v1", "llm_api_key": ""})
    assert "non raggiungibile" in page.text


def test_mailto_veloce_salva_e_conferma():
    page = client.post("/mailto", data={"mailto": "ricercatore@ateneo.it"})
    assert "ricercatore@ateneo.it" in page.text
    assert config_module.load().mailto == "ricercatore@ateneo.it"


def salva_impostazioni(**campi):
    dati = {"mailto": "", "llm_base_url": "", "llm_model": "",
            "llm_api_key": "", "core_api_key": "", "s2_api_key": "", "ncbi_api_key": ""}
    dati.update(campi)
    return client.post("/impostazioni", data=dati, follow_redirects=True)


def test_le_chiavi_non_finiscono_nell_html():
    salva_impostazioni(core_api_key="segretissima-123")
    pagina = client.get("/impostazioni")
    assert "segretissima-123" not in pagina.text
    assert "chiave impostata" in pagina.text


def test_un_campo_chiave_vuoto_conserva_la_chiave():
    salva_impostazioni(core_api_key="k-1")
    salva_impostazioni(mailto="x@y.it")  # chiavi non compilate
    config = config_module.load()
    assert config.core_api_key == "k-1"
    assert config.mailto == "x@y.it"


def test_la_spunta_rimuovi_cancella_la_chiave():
    salva_impostazioni(s2_api_key="k-2")
    salva_impostazioni(rimuovi=["s2_api_key"])
    assert config_module.load().s2_api_key == ""


def test_una_nuova_chiave_sostituisce_la_precedente():
    salva_impostazioni(ncbi_api_key="vecchia")
    salva_impostazioni(ncbi_api_key="nuova")
    assert config_module.load().ncbi_api_key == "nuova"
