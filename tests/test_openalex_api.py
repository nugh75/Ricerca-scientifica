import httpx
import respx

from ricerca import costo, openalex_api
from ricerca.config import Config


@respx.mock
async def test_la_chiamata_porta_chiave_ed_email():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"meta": {}, "results": []})
    )
    async with httpx.AsyncClient() as client:
        await openalex_api.chiama(
            client, "/works", Config(mailto="a@b.it", openalex_api_key="k"), filter="type:article"
        )
    indirizzo = str(rotta.calls[0].request.url)
    assert "api_key=k" in indirizzo
    assert "mailto=a%40b.it" in indirizzo
    assert "filter=type%3Aarticle" in indirizzo


@respx.mock
async def test_i_parametri_vuoti_non_partono():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"meta": {}, "results": []})
    )
    async with httpx.AsyncClient() as client:
        await openalex_api.chiama(client, "/works", Config(), search="", per_page="5")
    indirizzo = str(rotta.calls[0].request.url)
    assert "search=" not in indirizzo
    assert "mailto" not in indirizzo


@respx.mock
async def test_il_costo_dichiarato_finisce_nel_registro():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"meta": {"cost_usd": 0.001}, "results": []})
    )
    async with httpx.AsyncClient() as client:
        await openalex_api.chiama(client, "/works", Config())
    assert costo.speso() == 0.001


@respx.mock
async def test_una_risposta_dalla_cache_non_si_conta():
    from ricerca import cache

    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(
            200, json={"meta": {"cost_usd": 0.001}}, headers={cache.INTESTAZIONE: "1"}
        )
    )
    async with httpx.AsyncClient() as client:
        await openalex_api.chiama(client, "/works", Config())
    assert costo.speso() == 0.0


@respx.mock
async def test_un_errore_arriva_al_chiamante():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(429, json={"message": "budget finito"})
    )
    async with httpx.AsyncClient() as client:
        try:
            await openalex_api.chiama(client, "/works", Config())
        except httpx.HTTPStatusError as exc:
            assert exc.response.status_code == 429
        else:
            raise AssertionError("doveva sollevare")


def test_l_identificativo_si_accorcia():
    assert openalex_api.id_breve("https://openalex.org/W2741809807") == "W2741809807"
    assert openalex_api.id_breve("W123") == "W123"
    assert openalex_api.id_breve(None) == ""


def test_l_abstract_si_rimonta_dall_indice():
    indice = {"Il": [0], "gatto": [1, 4], "sul": [2], "tetto": [3], "dorme": [5]}
    assert openalex_api.abstract_da_indice(indice) == "Il gatto sul tetto gatto dorme"
    assert openalex_api.abstract_da_indice(None) is None
    assert openalex_api.abstract_da_indice({}) is None


def test_l_oql_si_legge_dalla_risposta():
    corpo = {"meta": {"x_query": {"oql": "works where year is (2024)"}}}
    assert openalex_api.oql(corpo) == "works where year is (2024)"
    assert openalex_api.oql({"meta": {}}) == ""
    assert openalex_api.oql({}) == ""


@respx.mock
async def test_l_oql_resta_nel_contesto_del_compito():
    import asyncio

    respx.get(url__startswith="https://api.openalex.org/works").mock(
        side_effect=lambda richiesta: httpx.Response(200, json={
            "meta": {"x_query": {"oql": str(richiesta.url.params.get("filter"))}}, "results": [],
        })
    )

    async def chiama_e_leggi(quale: str) -> str:
        async with httpx.AsyncClient() as client:
            await openalex_api.chiama(client, "/works", Config(), filter=quale)
        return openalex_api.ULTIMA_OQL.get("")

    uno, due = await asyncio.gather(chiama_e_leggi("uno"), chiama_e_leggi("due"))
    assert uno == "uno"
    assert due == "due"
