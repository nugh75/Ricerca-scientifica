import httpx
import respx

from ricerca import sources
from ricerca.config import Config
from ricerca.models import Block, Filtri, Strategy

RISPOSTA = {"meta": {"cost_usd": 0.001}, "results": [{
    "id": "https://openalex.org/W3", "title": "Vicino di significato",
    "publication_year": 2025, "authorships": [], "primary_location": {},
}]}


def test_la_fonte_e_registrata_ma_spenta_di_suo():
    assert "openalex_semantica" in sources.BY_ID
    assert "openalex_semantica" not in sources.DEFAULT_SELECTED


def test_la_query_e_il_testo_dei_termini_non_i_booleani():
    fonte = sources.BY_ID["openalex_semantica"]
    strategy = Strategy(blocks=[
        Block("Uno", ["ai literacy", "AI competence"]),
        Block("Due", ["teacher"]),
    ])
    resa = fonte.render_query(strategy)
    assert "OR" not in resa
    assert "ai literacy" in resa
    assert "teacher" in resa


@respx.mock
async def test_cerca_con_il_parametro_semantico():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["openalex_semantica"].search(
            client, "insegnare l'intelligenza artificiale", 25, Config()
        )
    indirizzo = str(rotta.calls[0].request.url)
    assert "search.semantic=" in indirizzo
    assert works[0].title == "Vicino di significato"
    assert works[0].sources == ["openalex_semantica"]


@respx.mock
async def test_non_si_chiedono_piu_di_cinquanta_risultati():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        await sources.BY_ID["openalex_semantica"].search(client, "x", 200, Config())
    assert "per_page=50" in str(rotta.calls[0].request.url)


@respx.mock
async def test_i_filtri_di_anno_valgono_anche_qui():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        await sources.BY_ID["openalex_semantica"].search(
            client, "x", 10, Config(), Filtri(anno_da=2020, escludi_ritirati=True)
        )
    indirizzo = str(rotta.calls[0].request.url)
    assert "from_publication_date%3A2020-01-01" in indirizzo
    assert "is_retracted%3Afalse" in indirizzo


def test_l_avviso_spiega_il_costo():
    testo = sources.BY_ID["openalex_semantica"].avviso(Config(), "it")
    assert "50" in testo
