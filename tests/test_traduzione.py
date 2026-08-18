import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import config as config_module
from ricerca.app import _sembra_italiano, app
from ricerca.config import Config
from ricerca.llm import LLMClient

client = TestClient(app)

CONCEPTS = {"concepts": []}
TOPICS = {"topics": []}
WORKS = {"results": []}
MESH = {"esearchresult": {"translationset": [{"from": "l", "to": '"literacy"[MeSH Terms]'}]}}


def test_riconosce_un_topic_italiano():
    assert _sembra_italiano("competenze di intelligenza artificiale negli insegnanti")
    assert _sembra_italiano("AI literacy in teacher education") is False


@respx.mock
async def test_traduci_chiede_solo_la_traduzione():
    rotta = respx.post("http://x/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": ' "AI literacy in teachers"\n'}}]})
    )
    testo = await LLMClient(Config(llm_base_url="http://x/v1", llm_model="m")).traduci(
        "competenze di IA negli insegnanti"
    )
    assert testo == "AI literacy in teachers"
    assert b"Traduci in inglese" in rotta.calls[0].request.content


@respx.mock
def test_il_topic_italiano_viene_tradotto_prima_di_interrogare_pubmed():
    config_module.save(Config(lang="it", llm_base_url="http://x/v1", llm_model="m"))
    respx.post("http://x/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "AI literacy in teachers"}}]})
    )
    respx.get(url__startswith="https://api.openalex.org/text/concepts").mock(return_value=httpx.Response(200, json=CONCEPTS))
    respx.get(url__startswith="https://api.openalex.org/text/topics").mock(return_value=httpx.Response(200, json=TOPICS))
    respx.get(url__startswith="https://api.openalex.org/works").mock(return_value=httpx.Response(200, json=WORKS))
    pubmed = respx.get(url__startswith="https://eutils.ncbi.nlm.nih.gov").mock(return_value=httpx.Response(200, json=MESH))

    pagina = client.post("/suggerimenti", data={"topic": "competenze di IA negli insegnanti"})

    assert "AI+literacy+in+teachers" in str(pubmed.calls[0].request.url)
    assert "Topic tradotto" in pagina.text


@respx.mock
def test_senza_llm_il_topic_resta_com_e():
    config_module.save(Config(lang="it"))
    respx.get(url__startswith="https://api.openalex.org/text/concepts").mock(return_value=httpx.Response(200, json=CONCEPTS))
    respx.get(url__startswith="https://api.openalex.org/text/topics").mock(return_value=httpx.Response(200, json=TOPICS))
    respx.get(url__startswith="https://api.openalex.org/works").mock(return_value=httpx.Response(200, json=WORKS))
    pubmed = respx.get(url__startswith="https://eutils.ncbi.nlm.nih.gov").mock(return_value=httpx.Response(200, json={"esearchresult": {}}))

    pagina = client.post("/suggerimenti", data={"topic": "competenze di IA negli insegnanti"})

    assert "competenze" in str(pubmed.calls[0].request.url)
    assert "nessun termine MeSH" in pagina.text
