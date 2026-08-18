import httpx
import respx

from ricerca import search, sources
from ricerca.config import Config
from ricerca.models import Block, Filtri, Strategy
from ricerca.strategy import strategy_from_form


def con_filtri(**kwargs):
    return Strategy([Block("C", ["AI literacy"])], mesh=["Literacy"], filtri=Filtri(**kwargs))


def test_gli_anni_arrivano_nella_sintassi_di_ogni_motore():
    s = con_filtri(anno_da=2019, anno_a=2026)
    assert '("2019"[dp] : "2026"[dp])' in sources.BY_ID["pubmed"].render_query(s)
    assert "PUB_YEAR:[2019 TO 2026]" in sources.BY_ID["europepmc"].render_query(s)
    assert "submittedDate:[20190101 TO 20261231]" in sources.BY_ID["arxiv"].render_query(s)
    assert "bibjson.year:[2019 TO 2026]" in sources.BY_ID["doaj"].render_query(s)
    assert "PUBYEAR > 2018" in sources.BY_ID["scopus"].render_query(s)
    assert "PY=(2019-2026)" in sources.BY_ID["wos"].render_query(s)


def test_solo_articoli_dove_il_motore_lo_prevede():
    s = con_filtri(solo_articoli=True)
    assert '("journal article"[pt])' in sources.BY_ID["pubmed"].render_query(s)
    assert "DOCTYPE(ar)" in sources.BY_ID["scopus"].render_query(s)
    assert "DT=(Article)" in sources.BY_ID["wos"].render_query(s)


def test_senza_filtri_la_query_resta_pulita():
    s = con_filtri()
    assert sources.BY_ID["pubmed"].render_query(s).endswith('("Literacy"[MeSH Terms])')
    assert "submittedDate" not in sources.BY_ID["arxiv"].render_query(s)


def test_solo_un_estremo_dell_intervallo():
    assert "PUB_YEAR:[2020 TO 3000]" in sources.BY_ID["europepmc"].render_query(con_filtri(anno_da=2020))
    assert "PUB_YEAR:[1800 TO 2010]" in sources.BY_ID["europepmc"].render_query(con_filtri(anno_a=2010))


def test_anni_non_validi_vengono_ignorati():
    s = strategy_from_form(["C"], ["x"], "", "milleottocento", "-5", False)
    assert s.filtri.anno_da is None and s.filtri.anno_a is None


@respx.mock
async def test_openalex_mette_i_filtri_nei_parametri():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    await sources.BY_ID["openalex"].search(
        httpx.AsyncClient(), "q", 5, Config(), Filtri(2019, 2026, True)
    )
    inviata = str(rotta.calls[0].request.url)
    assert "from_publication_date%3A2019-01-01" in inviata
    assert "to_publication_date%3A2026-12-31" in inviata
    assert "type%3Aarticle" in inviata


@respx.mock
async def test_semantic_scholar_usa_il_parametro_year():
    rotta = respx.get(url__startswith="https://api.semanticscholar.org").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    await sources.BY_ID["semanticscholar"].search(
        httpx.AsyncClient(), "q", 5, Config(), Filtri(anno_da=2019)
    )
    assert "year=2019-" in str(rotta.calls[0].request.url)


@respx.mock
async def test_crossref_parsing_e_filtri():
    rotta = respx.get(url__startswith="https://api.crossref.org/works").mock(
        return_value=httpx.Response(200, json={"message": {"items": [{
            "title": ["Establishing AI Literacy"],
            "author": [{"given": "Ada", "family": "Rossi"}],
            "issued": {"date-parts": [[2024, 3, 3]]},
            "DOI": "10.1080/x", "URL": "https://doi.org/10.1080/x",
            "container-title": ["The Science Teacher"],
            "abstract": "<jats:p>Testo</jats:p>",
        }]}})
    )
    works = await sources.BY_ID["crossref"].search(
        httpx.AsyncClient(), "q", 5, Config(), Filtri(anno_da=2020, solo_articoli=True)
    )
    assert works[0].year == 2024
    assert works[0].authors == ["Ada Rossi"]
    assert works[0].venue == "The Science Teacher"
    assert works[0].abstract == "Testo"  # niente marcatura JATS
    inviata = str(rotta.calls[0].request.url)
    assert "from-pub-date%3A2020-01-01" in inviata
    assert "type%3Ajournal-article" in inviata


@respx.mock
async def test_i_filtri_arrivano_alle_fonti_durante_la_ricerca():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    await search.run(con_filtri(anno_da=2021), ["openalex"], 5, Config())
    assert "from_publication_date%3A2021-01-01" in str(rotta.calls[0].request.url)
