import httpx
import pytest
import respx

from ricerca import keywords
from ricerca.config import Config

WORKS_RICCO = {"results": [
    {"title": "AI literacy in higher education",
     "topics": [{"display_name": "Online Learning and Analytics"}],
     "keywords": [{"display_name": "AI literacy"}, {"display_name": "digital competence"}]},
    {"title": "Higher education and AI literacy",
     "topics": [{"display_name": "Online Learning and Analytics"}],
     "keywords": [{"display_name": "AI literacy"}]}
]}
MESH = {
    "esearchresult": {
        "translationset": [{"from": "literacy", "to": '"literacy"[MeSH Terms] OR literacy[All Fields]'}],
        "querytranslation": '"artificial intelligence"[MeSH Terms] AND "literacy"[MeSH Terms]',
    }
}



def test_count_terms_preferisce_i_bigrammi_ed_esclude_le_stopword():
    titles = ["AI literacy in higher education", "Higher education and the AI literacy"]
    terms = dict(keywords.count_terms(titles, exclude="AI literacy"))
    assert terms["higher education"] == 2
    assert "the" not in terms
    assert "literacy" not in terms  # parola del topic, esclusa


@respx.mock
async def test_gather_raccoglie_da_tutte_le_fonti():
    respx.get(url__startswith=f"{keywords.OPENALEX}/works").mock(return_value=httpx.Response(200, json=WORKS_RICCO))
    respx.get(url__startswith=f"{keywords.EUTILS}/esearch.fcgi").mock(return_value=httpx.Response(200, json=MESH))

    async with httpx.AsyncClient() as client:
        result = await keywords.gather("AI literacy", client, Config())

    assert result.concepts[0] == ("AI literacy", 1.0)   # in tutti i risultati
    assert ("digital competence", 0.5) in result.concepts
    assert result.topics == ["Online Learning and Analytics"]
    assert result.mesh == ["literacy", "artificial intelligence"]
    assert ("higher education", 2) in result.cooccurring
    assert result.notes == []


@respx.mock
async def test_gather_isola_il_fallimento_di_una_fonte():
    respx.get(url__startswith=f"{keywords.OPENALEX}/works").mock(return_value=httpx.Response(200, json=WORKS_RICCO))
    respx.get(url__startswith=f"{keywords.EUTILS}/esearch.fcgi").mock(side_effect=httpx.ConnectError("giù"))

    async with httpx.AsyncClient() as client:
        result = await keywords.gather("AI literacy", client, Config())

    assert result.concepts  # OpenAlex ha risposto
    assert result.mesh == []
    assert any("MeSH" in nota for nota in result.notes)
    assert len(result.notes) == 1  # una chiamata sola, una nota sola


def test_words_of_separa_sull_apostrofo_italiano():
    assert keywords.words_of("L'uso dell'intelligenza artificiale") == ["uso", "intelligenza", "artificiale"]


def test_count_terms_non_produce_frammenti_di_elisione():
    terms = dict(keywords.count_terms(["Uso dell'IA a scuola", "Pratiche dell'IA a scuola"]))
    assert not any(t.startswith("dell") for t in terms)


@respx.mock
async def test_gather_avvisa_quando_mancano_i_mesh():
    respx.get(url__startswith=f"{keywords.OPENALEX}/works").mock(return_value=httpx.Response(200, json=WORKS_RICCO))
    respx.get(url__startswith=f"{keywords.EUTILS}/esearch.fcgi").mock(
        return_value=httpx.Response(200, json={"esearchresult": {}})
    )
    async with httpx.AsyncClient() as client:
        result = await keywords.gather("topic in italiano", client, Config(lang="it"))
    assert any("MeSH" in nota and "inglese" in nota for nota in result.notes)


def test_gli_acronimi_di_due_lettere_entrano_nei_bigrammi():
    terms = dict(keywords.count_terms(["AI literacy at school", "AI literacy for teachers"]))
    assert "ai literacy" in terms
    assert "ai" not in terms  # da solo e' troppo generico


@respx.mock
async def test_nota_leggibile_quando_openalex_limita_le_richieste():
    respx.get(url__startswith=f"{keywords.OPENALEX}/works").mock(return_value=httpx.Response(429))
    respx.get(url__startswith=f"{keywords.EUTILS}/esearch.fcgi").mock(return_value=httpx.Response(200, json=MESH))
    async with httpx.AsyncClient() as client:
        result = await keywords.gather("AI literacy", client, Config(lang="it"))
    assert any("email di cortesia" in nota for nota in result.notes)
