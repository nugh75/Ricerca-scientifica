import httpx
import respx

from ricerca import search
from ricerca.config import Config
from ricerca.models import Block, Strategy

OPENALEX_OK = {"results": [{"id": "https://openalex.org/W1", "title": "Uno", "publication_year": 2024,
                            "doi": "https://doi.org/10.1/x", "authorships": [], "primary_location": {}}]}
DOAJ_OK = {"results": [{"bibjson": {"title": "Uno", "year": "2024",
                                    "identifier": [{"type": "doi", "id": "10.1/X"}]}}]}


def test_queries_for_copre_tutte_le_fonti(strategy):
    queries = search.queries_for(strategy)
    assert set(queries) == set(s.id for s in search.sources_registry.ALL)


async def test_run_senza_fonti_o_con_strategia_vuota(config):
    assert await search.run(Strategy(), ["openalex"], 5, config) == ([], [])
    assert await search.run(Strategy([Block("a", ["x"])]), [], 5, config) == ([], [])


@respx.mock
async def test_run_deduplica_i_risultati_di_fonti_diverse(strategy, config):
    respx.get(url__startswith="https://api.openalex.org/works").mock(return_value=httpx.Response(200, json=OPENALEX_OK))
    respx.get(url__startswith="https://doaj.org").mock(return_value=httpx.Response(200, json=DOAJ_OK))

    results, works = await search.run(strategy, ["openalex", "doaj"], 5, config)

    assert len(works) == 1
    assert works[0].sources == ["openalex", "doaj"]
    assert all(r.error is None for r in results)


@respx.mock
async def test_una_fonte_rotta_non_ferma_le_altre(strategy, config):
    respx.get(url__startswith="https://api.openalex.org/works").mock(return_value=httpx.Response(200, json=OPENALEX_OK))
    respx.get(url__startswith="https://doaj.org").mock(return_value=httpx.Response(503))

    results, works = await search.run(strategy, ["openalex", "doaj"], 5, config)

    errori = {r.source_id: r.error for r in results}
    assert errori["openalex"] is None
    assert errori["doaj"] == "HTTP 503"
    assert len(works) == 1


async def test_fonte_senza_chiave_segnala_il_motivo(strategy, config):
    results, works = await search.run(strategy, ["core"], 5, config)
    assert "chiave" in results[0].error
    assert works == []
