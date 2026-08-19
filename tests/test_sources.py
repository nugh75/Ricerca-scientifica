import httpx
import respx

from ricerca import sources
from ricerca.config import Config
from ricerca.models import Block, Strategy
from ricerca.sources import opac_sbn


def test_ogni_fonte_ha_id_ed_etichetta():
    assert len(sources.ALL) == len(sources.BY_ID)
    assert all(s.id and s.label for s in sources.ALL)


def test_query_pubmed_usa_tiab_e_mesh(strategy):
    query = sources.BY_ID["pubmed"].render_query(strategy)
    assert query == (
        '("AI literacy"[tiab] OR "AI competence"[tiab]) AND ("teacher"[tiab] OR "educator"[tiab])'
        ' AND ("Artificial Intelligence"[MeSH Terms])'
    )


def test_query_specifiche_per_motore(strategy):
    assert sources.BY_ID["europepmc"].render_query(strategy).startswith('(TITLE_ABS:"AI literacy"')
    assert sources.BY_ID["arxiv"].render_query(strategy).startswith('(all:"AI literacy"')
    assert sources.BY_ID["scopus"].render_query(strategy).startswith("TITLE-ABS-KEY(")
    assert sources.BY_ID["wos"].render_query(strategy).startswith("TS=(")
    # Semantic Scholar e OPAC non capiscono i booleani
    assert sources.BY_ID["semanticscholar"].render_query(strategy) == (
        "AI literacy AI competence teacher educator"
    )


def test_core_disattivata_senza_chiave():
    assert sources.BY_ID["core"].unavailable_reason(Config()) is not None
    assert sources.BY_ID["core"].unavailable_reason(Config(core_api_key="k")) is None
    assert sources.BY_ID["openalex"].unavailable_reason(Config()) is None


@respx.mock
async def test_openalex_parsing():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"results": [{
            "id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.1145/3313831.3376727",
            "title": "What is AI Literacy?",
            "publication_year": 2020,
            "authorships": [{"author": {"display_name": "Duri Long"}}],
            "primary_location": {"source": {"display_name": "CHI"}},
            "best_oa_location": {"pdf_url": "https://x/paper.pdf"},
        }]})
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["openalex"].search(client, "q", 5, Config())
    assert works[0].title == "What is AI Literacy?"
    assert works[0].year == 2020
    assert works[0].authors == ["Duri Long"]
    assert works[0].venue == "CHI"
    assert works[0].oa_url == "https://x/paper.pdf"
    assert works[0].sources == ["openalex"]


@respx.mock
async def test_pubmed_parsing_due_chiamate():
    respx.get(url__startswith="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": ["42597755"]}})
    )
    respx.get(url__startswith="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(
        return_value=httpx.Response(200, json={"result": {
            "uids": ["42597755"],
            "42597755": {
                "uid": "42597755",
                "title": "Generative AI literacy and TPACK.",
                "pubdate": "2026 Jan",
                "source": "Front Psychol",
                "authors": [{"name": "Yang Z"}],
                "articleids": [{"idtype": "doi", "value": "10.3389/fpsyg.2026.1932185"}],
            },
        }})
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["pubmed"].search(client, "q", 5, Config())
    assert works[0].year == 2026
    assert works[0].doi == "10.3389/fpsyg.2026.1932185"
    assert works[0].url.endswith("/42597755/")


@respx.mock
async def test_pubmed_senza_risultati_non_chiama_esummary():
    respx.get(url__startswith="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": []}})
    )
    async with httpx.AsyncClient() as client:
        assert await sources.BY_ID["pubmed"].search(client, "q", 5, Config()) == []


@respx.mock
async def test_europepmc_parsing():
    respx.get(url__startswith="https://www.ebi.ac.uk/europepmc").mock(
        return_value=httpx.Response(200, json={"resultList": {"result": [{
            "id": "426", "source": "MED", "title": "Emotional pathways", "pubYear": "2026",
            "doi": "10.3389/fpsyg.2026.1872841", "journalTitle": "Front Psychol",
            "authorString": "Bao D, Du J.", "abstractText": "testo",
        }]}})
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["europepmc"].search(client, "q", 5, Config())
    assert works[0].authors == ["Bao D", "Du J."]
    assert works[0].abstract == "testo"


@respx.mock
async def test_arxiv_parsing_atom():
    atom = """<?xml version='1.0' encoding='UTF-8'?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <published>2024-01-01T00:00:00Z</published>
        <title>AI literacy
          for teachers</title>
        <summary>Un abstract.</summary>
        <author><name>Anna Bianchi</name></author>
        <link title="pdf" href="http://arxiv.org/pdf/2401.00001v1"/>
      </entry>
    </feed>"""
    respx.get(url__startswith="https://export.arxiv.org").mock(return_value=httpx.Response(200, text=atom))
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["arxiv"].search(client, "q", 5, Config())
    assert works[0].title == "AI literacy for teachers"
    assert works[0].year == 2024
    assert works[0].oa_url.endswith(".00001v1")


@respx.mock
async def test_doaj_parsing():
    respx.get(url__startswith="https://doaj.org/api/search/articles").mock(
        return_value=httpx.Response(200, json={"results": [{"bibjson": {
            "title": "AI literacy",
            "year": "2025",
            "identifier": [{"type": "doi", "id": "10.1016/j.caeai.2025.100451"}],
            "author": [{"name": "Mario Rossi"}],
            "journal": {"title": "Computers and Education: AI"},
            "link": [{"url": "https://doi.org/10.1016/x"}],
        }}]})
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["doaj"].search(client, "q", 5, Config())
    assert works[0].year == 2025
    assert works[0].venue == "Computers and Education: AI"


@respx.mock
async def test_semantic_scholar_spiega_il_429():
    respx.get(url__startswith="https://api.semanticscholar.org").mock(return_value=httpx.Response(429))
    async with httpx.AsyncClient() as client:
        try:
            await sources.BY_ID["semanticscholar"].search(client, "q", 5, Config())
        except RuntimeError as exc:
            assert "key" in str(exc)
        else:
            raise AssertionError("doveva sollevare un errore")


def test_opac_parse_tollera_forme_diverse():
    works = opac_sbn.parse('{"records": [{"title": "Intelligenza artificiale", "year": "2023", "bid": "ABC"}]}')
    assert works[0].year == 2023
    assert works[0].url.endswith("ABC")
    assert opac_sbn.parse("{}") == []


@respx.mock
async def test_europepmc_sede_di_un_preprint_non_stampa_un_dizionario():
    respx.get(url__startswith="https://www.ebi.ac.uk/europepmc").mock(
        return_value=httpx.Response(200, json={"resultList": {"result": [{
            "id": "1", "source": "PPR", "title": "Teacher AI Literacy", "pubYear": "2026",
            "journalTitle": None, "authorString": "Chowdhury S.",
            "bookOrReportDetails": {"publisher": "Research Square", "yearOfPublication": 2026},
        }]}})
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["europepmc"].search(client, "q", 5, Config())
    assert works[0].venue == "Research Square"


def test_gli_abstract_arrivano_senza_marcatura():
    """Europe PMC li manda con tag JATS dentro: a schermo si leggevano
    «<h4>Introduction</h4>This study…»."""

    from ricerca.sources.base import testo

    assert testo("<h4>Introduction</h4>This study presents…") == "Introduction This study presents…"
    assert testo("<jats:p>Testo</jats:p>") == "Testo"
    assert testo("  spazi   ripetuti  ") == "spazi ripetuti"
    assert testo(None) is None
    assert testo("<p></p>") is None


@respx.mock
async def test_europepmc_ripulisce_l_abstract():
    respx.get(url__startswith="https://www.ebi.ac.uk/europepmc").mock(
        return_value=httpx.Response(200, json={"resultList": {"result": [{
            "id": "1", "source": "MED", "title": "Uno", "pubYear": "2026",
            "abstractText": "<h4>Introduction</h4>Questo studio…",
        }]}})
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["europepmc"].search(client, "q", 5, Config())
    assert works[0].abstract == "Introduction Questo studio…"
    assert "<" not in works[0].abstract
