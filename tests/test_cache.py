import httpx
import pytest
import respx

from ricerca import cache


@pytest.fixture
def cache_accesa(monkeypatch, isolated_config):
    monkeypatch.setenv("RICERCA_CACHE", "1")
    cache.svuota()
    return isolated_config


@respx.mock
async def test_la_seconda_richiesta_non_tocca_la_rete(cache_accesa):
    rotta = respx.get("https://api.esempio.org/works").mock(
        return_value=httpx.Response(200, json={"results": [1]})
    )
    async with cache.client() as client:
        prima = await client.get("https://api.esempio.org/works")
        seconda = await client.get("https://api.esempio.org/works")

    assert rotta.call_count == 1
    assert prima.json() == seconda.json() == {"results": [1]}


@respx.mock
async def test_query_diverse_restano_distinte(cache_accesa):
    rotta = respx.get(url__startswith="https://api.esempio.org/works").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    async with cache.client() as client:
        await client.get("https://api.esempio.org/works", params={"q": "uno"})
        await client.get("https://api.esempio.org/works", params={"q": "due"})
    assert rotta.call_count == 2


@respx.mock
async def test_gli_errori_non_finiscono_in_cache(cache_accesa):
    rotta = respx.get("https://api.esempio.org/rotto").mock(return_value=httpx.Response(429))
    async with cache.client() as client:
        await client.get("https://api.esempio.org/rotto")
        await client.get("https://api.esempio.org/rotto")
    assert rotta.call_count == 2


@respx.mock
async def test_una_voce_scaduta_viene_richiesta_di_nuovo(cache_accesa, monkeypatch):
    rotta = respx.get("https://api.esempio.org/w").mock(return_value=httpx.Response(200, json={}))
    async with httpx.AsyncClient(transport=cache.TrasportoConCache(durata=0)) as client:
        await client.get("https://api.esempio.org/w")
        await client.get("https://api.esempio.org/w")
    assert rotta.call_count == 2


@respx.mock
async def test_spenta_la_cache_ogni_richiesta_passa(monkeypatch, isolated_config):
    monkeypatch.setenv("RICERCA_CACHE", "0")
    rotta = respx.get("https://api.esempio.org/w").mock(return_value=httpx.Response(200, json={}))
    async with cache.client() as client:
        await client.get("https://api.esempio.org/w")
        await client.get("https://api.esempio.org/w")
    assert rotta.call_count == 2


@respx.mock
async def test_una_risposta_compressa_non_viene_decompressa_due_volte(cache_accesa):
    import gzip

    corpo = gzip.compress(b'{"esearchresult": {"idlist": ["1"]}}')
    respx.get("https://eutils.esempio.org/esearch").mock(
        return_value=httpx.Response(
            200, content=corpo, headers={"content-encoding": "gzip", "content-type": "application/json"}
        )
    )
    async with cache.client() as client:
        prima = await client.get("https://eutils.esempio.org/esearch")
        seconda = await client.get("https://eutils.esempio.org/esearch")

    assert prima.json()["esearchresult"]["idlist"] == ["1"]
    assert seconda.json() == prima.json()
