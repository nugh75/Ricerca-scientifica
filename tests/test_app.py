import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import config as config_module
from ricerca.app import app
from ricerca.config import Config

client = TestClient(app)

MESH = {"esearchresult": {"translationset": [{"from": "l", "to": '"literacy"[MeSH Terms]'}]}}
WORKS_TITLES = {"results": [
    {"title": "AI literacy in higher education", "keywords": [{"display_name": "Literacy"}]},
    {"title": "higher education AI", "keywords": []},
]}
WORKS_FULL = {"results": [{"id": "https://openalex.org/W1", "title": "Uno", "publication_year": 2024,
                           "doi": "https://doi.org/10.1/x", "authorships": [{"author": {"display_name": "A. Rossi"}}],
                           "primary_location": {"source": {"display_name": "Rivista"}}}]}


def test_home_mostra_il_form():
    config_module.save(Config(configurato="1"))
    page = client.get("/")
    assert page.status_code == 200
    assert "Suggest keywords" in page.text
    assert "No LLM configured" in page.text


@respx.mock
def test_suggerimenti_costruisce_i_blocchi_senza_llm():
    respx.get(url__startswith="https://api.openalex.org/works").mock(return_value=httpx.Response(200, json=WORKS_TITLES))
    respx.get(url__startswith="https://eutils.ncbi.nlm.nih.gov").mock(return_value=httpx.Response(200, json=MESH))

    page = client.post("/suggerimenti", data={"topic": "AI literacy"})

    assert page.status_code == 200
    assert "Literacy" in page.text
    assert "higher education" in page.text
    assert "blocks built from the data alone" in page.text
    assert "no search has run yet" in page.text  # il passo 2 non cerca da solo
    assert "TITLE-ABS-KEY(" in page.text  # la stringa Scopus e' gia' pronta


def test_query_rende_le_stringhe_per_ogni_motore():
    page = client.post("/query", data={"label": ["Concetto"], "terms": ["AI literacy, AI competence"], "mesh": ""})
    assert '(&#34;AI literacy&#34; OR &#34;AI competence&#34;)' in page.text
    assert "tiab" in page.text


@respx.mock
def test_cerca_mostra_risultati_ed_export(esegui_ricerca):
    respx.get(url__startswith="https://api.openalex.org/works").mock(return_value=httpx.Response(200, json=WORKS_FULL))
    respx.get(url__startswith="https://doaj.org").mock(return_value=httpx.Response(500))

    page = esegui_ricerca(client, {
        "label": ["Concetto"], "terms": ["AI literacy"], "mesh": "",
        "fonte": ["openalex", "doaj"], "limite": "5",
    })

    assert "Uno" in page.text
    assert "HTTP 500" in page.text
    token = page.text.split("/export/")[1].split(".bib")[0]

    bib = client.get(f"/export/{token}.bib")
    assert "@article{" in bib.text
    csv = client.get(f"/export/{token}.csv")
    assert csv.text.startswith("anno,titolo,autori,sede,fonti")


def test_impostazioni_salva_su_file(isolated_config):
    risposta = client.post("/impostazioni", data={
        "mailto": "x@y.it", "llm_base_url": "http://localhost:11434/v1", "llm_model": "qwen3:8b",
        "llm_api_key": "", "core_api_key": "", "s2_api_key": "", "ncbi_api_key": "",
    }, follow_redirects=True)
    assert risposta.status_code == 200
    assert config_module.load().llm_model == "qwen3:8b"
    assert "saved to" in risposta.text


@respx.mock
def test_elenco_modelli_riporta_errore_leggibile():
    respx.get("http://spento/v1/models").mock(side_effect=httpx.ConnectError("connessione rifiutata"))
    page = client.post("/impostazioni/modelli", data={"llm_base_url": "http://spento/v1", "llm_api_key": ""})
    assert "unreachable" in page.text


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
    assert "key set" in pagina.text


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


WORKS_OA = {"results": [{
    "id": "https://openalex.org/W9", "title": "Aperto", "publication_year": 2025,
    "doi": "https://doi.org/10.1/oa", "authorships": [{"author": {"display_name": "Duri Long"}}],
    "primary_location": {"source": {"display_name": "Rivista"}},
    "best_oa_location": {"pdf_url": "https://esempio.org/aperto.pdf"},
}]}


def cerca_finta(attendi, **extra):
    dati = {"label": ["Concetto"], "terms": ["AI literacy"], "mesh": "",
            "fonte": ["openalex"], "limite": "5", "topic": "AI literacy"}
    dati.update(extra)
    return attendi(client, dati)


@respx.mock
def test_la_ricerca_finisce_in_cronologia_ed_e_riapribile(esegui_ricerca):
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=WORKS_OA))

    pagina = cerca_finta(esegui_ricerca)
    id_ricerca = pagina.text.split("/export/")[1].split(".bib")[0]

    cronologia = client.get("/cronologia")
    assert "AI literacy" in cronologia.text

    salvata = client.get(f"/cronologia/{id_ricerca}")
    assert "Aperto" in salvata.text
    assert "Saved search" in salvata.text


@respx.mock
def test_i_campi_scelti_cambiano_tabella_ed_export(esegui_ricerca):
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=WORKS_OA))
    pagina = cerca_finta(esegui_ricerca)
    id_ricerca = pagina.text.split("/export/")[1].split(".bib")[0]

    elenco = client.post(f"/risultati/{id_ricerca}", data={"campo": ["doi", "titolo"], "vista": "tabella"})
    assert "10.1/oa" in elenco.text
    assert "Rivista" not in elenco.text  # la sede non è più selezionata

    csv = client.get(f"/export/{id_ricerca}.csv?campi=doi,titolo")
    assert csv.text.splitlines()[0] == "doi,titolo"


@respx.mock
def test_vista_apa_ed_export_dei_riferimenti(esegui_ricerca):
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=WORKS_OA))
    pagina = cerca_finta(esegui_ricerca)
    id_ricerca = pagina.text.split("/export/")[1].split(".bib")[0]

    apa = client.post(f"/risultati/{id_ricerca}", data={"vista": "apa"})
    assert "Long, D. (2025). Aperto. Rivista. https://doi.org/10.1/oa" in apa.text

    scaricato = client.get(f"/export/{id_ricerca}.apa.txt")
    assert scaricato.text.startswith("Long, D. (2025).")


@respx.mock
def test_scaricamento_del_pdf_aperto_e_apertura(esegui_ricerca):
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=WORKS_OA))
    respx.get("https://esempio.org/aperto.pdf").mock(
        return_value=httpx.Response(200, content=b"%PDF-1.7\n%%EOF\n"))

    pagina = cerca_finta(esegui_ricerca)
    id_ricerca = pagina.text.split("/export/")[1].split(".bib")[0]

    cella = client.post(f"/pdf/{id_ricerca}/0")
    assert "open PDF" in cella.text

    file_pdf = client.get(f"/pdf/{id_ricerca}/0/file")
    assert file_pdf.status_code == 200
    assert file_pdf.content.startswith(b"%PDF")


@respx.mock
def test_un_pdf_irraggiungibile_lascia_un_messaggio(esegui_ricerca):
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=WORKS_OA))
    respx.get("https://esempio.org/aperto.pdf").mock(return_value=httpx.Response(403))

    pagina = cerca_finta(esegui_ricerca)
    id_ricerca = pagina.text.split("/export/")[1].split(".bib")[0]
    cella = client.post(f"/pdf/{id_ricerca}/0")
    assert "PDF not downloaded" in cella.text
    assert client.get(f"/pdf/{id_ricerca}/0/file").status_code == 404


def test_eliminazione_e_svuotamento_dalla_cronologia():
    from ricerca import history
    from ricerca.models import Block, Strategy

    id_voce = history.salva("vecchia", Strategy([Block("c", ["x"])]), [], [])
    client.post(f"/cronologia/{id_voce}/elimina", follow_redirects=True)
    assert history.voce(id_voce) is None

    history.salva("altra", Strategy([Block("c", ["x"])]), [], [])
    client.post("/cronologia/svuota", follow_redirects=True)
    assert history.elenco() == []


@respx.mock
def test_l_argomento_arriva_in_cronologia_dal_modulo_della_strategia():
    respx.get(url__startswith="https://api.openalex.org/works").mock(return_value=httpx.Response(200, json=WORKS_TITLES))
    respx.get(url__startswith="https://eutils.ncbi.nlm.nih.gov").mock(return_value=httpx.Response(200, json=MESH))

    pagina = client.post("/suggerimenti", data={"topic": "AI literacy"})
    assert '<input type="hidden" name="topic" value="AI literacy">' in pagina.text
