import httpx
import pytest
import respx

from ricerca.config import Config
from ricerca.llm import LLMClient, LLMError, _parse_blocks

RISPOSTA = {"choices": [{"message": {"content": '```json\n{"blocks": [{"label": "Concetto", "terms": ["a", "b"]}]}\n```'}}]}


def test_parse_blocks_accetta_json_dentro_i_backtick():
    blocks = _parse_blocks('```json\n{"blocks":[{"label":"L","terms":["x","y"]}]}\n```')
    assert blocks[0].label == "L"
    assert blocks[0].terms == ["x", "y"]


def test_parse_blocks_rifiuta_risposte_senza_json():
    with pytest.raises(LLMError):
        _parse_blocks("mi dispiace, non posso")


def test_parse_blocks_rifiuta_blocchi_vuoti():
    with pytest.raises(LLMError):
        _parse_blocks('{"blocks": [{"label": "L", "terms": []}]}')


@respx.mock
async def test_blocks_for_interroga_endpoint_openai_compatibile():
    route = respx.post("http://localhost:11434/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    config = Config(llm_base_url="http://localhost:11434/v1", llm_model="qwen3:8b")
    blocks = await LLMClient(config).blocks_for("topic", [("Literacy", 0.5)], [("higher education", 3)], ["AI"])

    assert blocks[0].terms == ["a", "b"]
    inviato = route.calls[0].request
    assert b"qwen3:8b" in inviato.content
    assert "Authorization" not in inviato.headers  # nessuna chiave per i modelli locali


@respx.mock
async def test_list_models_ordina_gli_id():
    respx.get("http://x/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "b"}, {"id": "a"}]})
    )
    assert await LLMClient(Config(llm_base_url="http://x/v1", llm_model="m")).list_models() == ["a", "b"]
