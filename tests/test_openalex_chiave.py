import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import config as config_module
from ricerca import keywords, sources
from ricerca.app import app
from ricerca.config import Config

client = TestClient(app)
WORKS = {"results": [{"title": "x", "keywords": [], "topics": []}]}


@respx.mock
async def test_la_chiave_accompagna_la_ricerca():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=WORKS)
    )
    async with httpx.AsyncClient() as http:
        await sources.BY_ID["openalex"].search(http, "q", 5, Config(openalex_api_key="k-123"))
    assert "api_key=k-123" in str(rotta.calls[0].request.url)


@respx.mock
async def test_la_chiave_accompagna_anche_i_suggerimenti():
    rotta = respx.get(url__startswith=f"{keywords.OPENALEX}/works").mock(
        return_value=httpx.Response(200, json=WORKS)
    )
    async with httpx.AsyncClient() as http:
        await keywords._openalex("topic", http, Config(openalex_api_key="k-123"))
    assert "api_key=k-123" in str(rotta.calls[0].request.url)


@respx.mock
async def test_senza_chiave_non_si_manda_il_parametro():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=WORKS)
    )
    async with httpx.AsyncClient() as http:
        await sources.BY_ID["openalex"].search(http, "q", 5, Config())
    assert "api_key" not in str(rotta.calls[0].request.url)


def test_l_avviso_sparisce_quando_la_chiave_c_e():
    assert sources.BY_ID["openalex"].avviso(Config(), "it") is not None
    assert sources.BY_ID["openalex"].avviso(Config(openalex_api_key="k"), "it") is None


def test_la_chiave_si_salva_dalle_impostazioni_e_non_torna_nell_html():
    client.post("/impostazioni", data={
        "mailto": "", "llm_base_url": "", "llm_model": "", "llm_api_key": "",
        "core_api_key": "", "s2_api_key": "", "ncbi_api_key": "",
        "openalex_api_key": "segreta-openalex", "zotero_api_key": "",
        "zotero_library_id": "", "zotero_library_type": "users",
    }, follow_redirects=True)

    assert config_module.load().openalex_api_key == "segreta-openalex"
    pagina = client.get("/impostazioni").text
    assert "segreta-openalex" not in pagina
    assert "OpenAlex key" in pagina


def test_la_guida_iniziale_la_chiede_e_la_salva():
    assert "openalex.org/rest-api" in client.get("/benvenuto").text
    client.post("/benvenuto", data={
        "mailto": "", "llm_base_url": "", "llm_model": "", "llm_api_key": "",
        "core_api_key": "", "s2_api_key": "", "ncbi_api_key": "",
        "openalex_api_key": "dalla-guida", "zotero_api_key": "",
        "zotero_library_id": "", "lingua": "en", "tema": "auto",
    })
    assert config_module.load().openalex_api_key == "dalla-guida"


def test_la_spunta_rimuovi_cancella_anche_questa():
    config_module.save(Config(openalex_api_key="da-togliere"))
    client.post("/impostazioni", data={
        "mailto": "", "llm_base_url": "", "llm_model": "", "llm_api_key": "",
        "core_api_key": "", "s2_api_key": "", "ncbi_api_key": "", "openalex_api_key": "",
        "zotero_api_key": "", "zotero_library_id": "", "zotero_library_type": "users",
        "rimuovi": ["openalex_api_key"],
    }, follow_redirects=True)
    assert config_module.load().openalex_api_key == ""
