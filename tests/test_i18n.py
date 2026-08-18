import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import config as config_module
from ricerca import i18n, search
from ricerca.app import app
from ricerca.config import Config
from ricerca.models import Block, Strategy

client = TestClient(app)


def test_le_due_lingue_hanno_le_stesse_chiavi():
    assert set(i18n.STRINGS["it"]) == set(i18n.STRINGS["en"])


def test_normalize_ricade_sull_inglese():
    assert i18n.normalize("it") == "it"
    assert i18n.normalize("de") == "en"
    assert i18n.normalize(None) == "en"


def test_il_cambio_lingua_persiste_nella_configurazione():
    pagina = client.post("/lingua/it", follow_redirects=True)
    assert "Suggerisci le parole chiave" in pagina.text
    assert config_module.load().lang == "it"

    pagina = client.post("/lingua/en", follow_redirects=True)
    assert "Describe the topic" in pagina.text
    assert config_module.load().lang == "en"


def test_le_impostazioni_non_azzerano_la_lingua():
    client.post("/lingua/it")
    client.post("/impostazioni", data={
        "mailto": "x@y.it", "llm_base_url": "", "llm_model": "",
        "llm_api_key": "", "core_api_key": "", "s2_api_key": "", "ncbi_api_key": "",
    })
    assert config_module.load().lang == "it"


async def test_i_motivi_delle_fonti_seguono_la_lingua():
    strategy = Strategy([Block("c", ["x"])])
    results, _ = await search.run(strategy, ["core"], 5, Config(lang="en"))
    assert results[0].error == "needs a free key from core.ac.uk/services/api"

    results, _ = await search.run(strategy, ["core"], 5, Config(lang="it"))
    assert "chiave gratuita" in results[0].error


@respx.mock
async def test_le_note_dei_suggerimenti_seguono_la_lingua():
    from ricerca import keywords

    respx.get(url__startswith=f"{keywords.OPENALEX}/works").mock(return_value=httpx.Response(200, json={"results": []}))
    respx.get(url__startswith=f"{keywords.EUTILS}/esearch.fcgi").mock(return_value=httpx.Response(200, json={"esearchresult": {}}))

    async with httpx.AsyncClient() as http:
        result = await keywords.gather("AI literacy", http, Config(lang="en"))
    assert any("no MeSH terms" in nota for nota in result.notes)


def test_nessuna_etichetta_di_fonte_e_solo_italiana():
    from ricerca import sources

    assert sources.BY_ID["opacsbn"].label == "OPAC SBN"


@respx.mock
async def test_il_prompt_dell_llm_chiede_le_etichette_nella_lingua_scelta():
    from ricerca.llm import LLMClient

    risposta = {"choices": [{"message": {"content": '{"blocks":[{"label":"L","terms":["x"]}]}'}}]}
    route = respx.post("http://x/v1/chat/completions").mock(return_value=httpx.Response(200, json=risposta))
    config = Config(llm_base_url="http://x/v1", llm_model="m")
    await LLMClient(config).blocks_for("topic", [], [], [], "en")
    assert b"in English" in route.calls[0].request.content
