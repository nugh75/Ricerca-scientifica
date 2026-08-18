import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from ricerca import config as config_module
from ricerca import history, zotero
from ricerca.app import app
from ricerca.config import Config
from ricerca.models import Block, SourceResult, Strategy, Work

client = TestClient(app)


def configurata():
    return Config(zotero_api_key="k", zotero_library_id="123")


def test_la_voce_ha_il_formato_che_zotero_si_aspetta():
    voce = zotero.voce(Work(
        title="AI literacy", authors=["Duri Long", "Platone"], year=2020,
        venue="CHI", doi="https://doi.org/10.1/x", sources=["openalex"],
    ))
    assert voce["itemType"] == "journalArticle"
    assert voce["creators"][0] == {"creatorType": "author", "firstName": "Duri", "lastName": "Long"}
    assert voce["creators"][1] == {"creatorType": "author", "name": "Platone"}
    assert voce["DOI"] == "10.1/x"          # senza il prefisso doi.org
    assert voce["tags"] == [{"tag": "openalex"}]


async def test_senza_chiave_non_si_invia_nulla():
    with pytest.raises(zotero.ZoteroError):
        await zotero.invia([Work(title="x")], Config(), httpx.AsyncClient())


@respx.mock
async def test_invio_riuscito_conta_i_record():
    rotta = respx.post("https://api.zotero.org/users/123/items").mock(
        return_value=httpx.Response(200, json={"successful": {"0": {}}, "unchanged": {}, "failed": {}})
    )
    esito = await zotero.invia([Work(title="x")], configurata(), httpx.AsyncClient())
    assert esito == {"inviati": 1, "falliti": 0}
    assert rotta.calls[0].request.headers["Zotero-API-Key"] == "k"


@respx.mock
async def test_i_lotti_grandi_vengono_spezzati():
    rotta = respx.post("https://api.zotero.org/users/123/items").mock(
        return_value=httpx.Response(200, json={"successful": {}, "failed": {}})
    )
    await zotero.invia([Work(title=f"n{i}") for i in range(120)], configurata(), httpx.AsyncClient())
    assert rotta.call_count == 3  # 50 + 50 + 20


@respx.mock
async def test_una_chiave_rifiutata_si_spiega():
    respx.post("https://api.zotero.org/users/123/items").mock(return_value=httpx.Response(403))
    with pytest.raises(zotero.ZoteroError, match="rifiutata"):
        await zotero.invia([Work(title="x")], configurata(), httpx.AsyncClient())


@respx.mock
def test_la_rotta_invia_solo_i_record_inclusi():
    config_module.save(configurata())
    works = [Work(title=f"Studio {n}", doi=f"10.1/{n}") for n in range(3)]
    id_ricerca = history.salva("t", Strategy([Block("c", ["x"])]),
                               [SourceResult("openalex", "OpenAlex", "q", works=works)], works)
    history.decide(id_ricerca, 1, "incluso")

    rotta = respx.post("https://api.zotero.org/users/123/items").mock(
        return_value=httpx.Response(200, json={"successful": {"0": {}}, "failed": {}})
    )
    pagina = client.post(f"/zotero/{id_ricerca}")

    inviati = rotta.calls[0].request.content
    assert b"Studio 1" in inviati and b"Studio 0" not in inviati
    assert "included records only" in pagina.text
