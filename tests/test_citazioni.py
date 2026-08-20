import httpx
import pytest
import respx

from ricerca import citazioni
from ricerca.config import Config
from ricerca.models import Work


def lavoro() -> Work:
    return Work(title="Il seme", openalex_id="W1", sources=["openalex"])


def risultato(*ids):
    return {"meta": {"cost_usd": 0.0001}, "results": [
        {"id": f"https://openalex.org/{i}", "title": f"Trovato {i}",
         "authorships": [], "primary_location": {}} for i in ids
    ]}


@respx.mock
async def test_avanti_chiede_chi_lo_cita():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=risultato("W9"))
    )
    async with httpx.AsyncClient() as client:
        trovati = await citazioni.cerca(lavoro(), "avanti", Config(), client)
    assert "cites%3AW1" in str(rotta.calls[0].request.url)
    assert trovati[0].openalex_id == "W9"
    assert trovati[0].sources == ["openalex"]


@respx.mock
async def test_indietro_legge_la_bibliografia_e_poi_i_record():
    respx.get(url__startswith="https://api.openalex.org/works/W1").mock(
        return_value=httpx.Response(200, json={
            "meta": {"cost_usd": 0.0},
            "id": "https://openalex.org/W1",
            "referenced_works": ["https://openalex.org/W7", "https://openalex.org/W8"],
        })
    )
    respx.get(url__startswith="https://api.openalex.org/works?").mock(
        return_value=httpx.Response(200, json=risultato("W7", "W8"))
    )
    async with httpx.AsyncClient() as client:
        trovati = await citazioni.cerca(lavoro(), "indietro", Config(), client)
    assert [w.openalex_id for w in trovati] == ["W7", "W8"]


@respx.mock
async def test_di_lato_usa_i_lavori_vicini():
    respx.get(url__startswith="https://api.openalex.org/works/W1").mock(
        return_value=httpx.Response(200, json={
            "meta": {}, "id": "https://openalex.org/W1",
            "related_works": ["https://openalex.org/W5"],
        })
    )
    respx.get(url__startswith="https://api.openalex.org/works?").mock(
        return_value=httpx.Response(200, json=risultato("W5"))
    )
    async with httpx.AsyncClient() as client:
        trovati = await citazioni.cerca(lavoro(), "lato", Config(), client)
    assert trovati[0].openalex_id == "W5"


@respx.mock
async def test_i_blocchi_sono_da_cento():
    ids = [f"W{n}" for n in range(1, 151)]
    rotta = respx.get(url__startswith="https://api.openalex.org/works?").mock(
        return_value=httpx.Response(200, json=risultato("W1"))
    )
    async with httpx.AsyncClient() as client:
        await citazioni.per_id(ids, Config(), client)
    assert len(rotta.calls) == 2


async def test_un_record_senza_identificativo_lo_dice():
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await citazioni.cerca(Work(title="Da Crossref"), "avanti", Config(), client)


@respx.mock
async def test_un_record_non_openalex_si_risolve_dal_doi():
    risoluzione = respx.get(
        url__startswith="https://api.openalex.org/works/https://doi.org/10.1186/prova"
    ).mock(return_value=httpx.Response(200, json={
        "id": "https://openalex.org/W1", "doi": "https://doi.org/10.1186/prova",
        "title": "Il seme trovato dal DOI", "authorships": [], "primary_location": {},
    }))
    citanti = respx.get(url__startswith="https://api.openalex.org/works?").mock(
        return_value=httpx.Response(200, json=risultato("W9"))
    )

    async with httpx.AsyncClient() as client:
        trovati = await citazioni.cerca(
            Work(title="Da PubMed", doi="10.1186/prova", sources=["pubmed"]),
            "avanti", Config(), client,
        )

    assert risoluzione.called
    assert "cites%3AW1" in str(citanti.calls[0].request.url)
    assert [w.openalex_id for w in trovati] == ["W9"]


@respx.mock
async def test_senza_doi_un_titolo_compatibile_si_puo_risolvere():
    chiamate = respx.get(url__startswith="https://api.openalex.org/works").mock(
        side_effect=[
            httpx.Response(200, json=risultato("W1") | {"results": [{
                "id": "https://openalex.org/W1",
                "title": "Un titolo abbastanza lungo da identificare senza DOI",
                "publication_year": 2024,
                "authorships": [], "primary_location": {},
            }]}),
            httpx.Response(200, json=risultato("W9")),
        ]
    )

    async with httpx.AsyncClient() as client:
        trovati = await citazioni.cerca(
            Work(
                title="Un titolo abbastanza lungo da identificare senza DOI",
                year=2024, sources=["crossref"],
            ),
            "avanti", Config(), client,
        )

    assert "search=" in str(chiamate.calls[0].request.url)
    assert "cites%3AW1" in str(chiamate.calls[1].request.url)
    assert [w.openalex_id for w in trovati] == ["W9"]


@respx.mock
async def test_senza_doi_non_accetta_un_risultato_solo_vagamente_simile():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=risultato("W2") | {"results": [{
            "id": "https://openalex.org/W2",
            "title": "Un altro lavoro che tratta un argomento solo vagamente simile",
            "publication_year": 2024,
            "authorships": [], "primary_location": {},
        }]})
    )

    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await citazioni.cerca(
                Work(
                    title="Un titolo abbastanza lungo da identificare senza DOI",
                    year=2024, sources=["crossref"],
                ),
                "avanti", Config(), client,
            )


async def test_un_verso_inventato_lo_dice():
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await citazioni.cerca(lavoro(), "diagonale", Config(), client)
