"""Test a contratto: interrogano davvero le API e controllano che i campi
su cui poggiano i parser esistano ancora.

Non girano con la suite normale (`-m "not rete"` è il valore predefinito):
li esegue la CI una volta a settimana, e si possono lanciare a mano con

    pytest -m rete
"""

import httpx
import pytest

from ricerca import keywords, sources
from ricerca.config import Config
from ricerca.models import Block, Filtri, Strategy

pytestmark = pytest.mark.rete

STRATEGIA = Strategy([Block("C", ["AI literacy"])], filtri=Filtri(anno_da=2018))
CONFIG = Config()


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        headers={"User-Agent": "ricerca-contratto/1.0"}, follow_redirects=True
    ) as sessione:
        yield sessione


def _salta_se_limitata(errore: Exception, fonte: str):
    """Un 429 è un limite di richieste, non un contratto rotto."""

    if isinstance(errore, httpx.HTTPStatusError) and errore.response.status_code == 429:
        pytest.skip(f"{fonte}: limite di richieste raggiunto (429)")
    raise errore


async def _controlla(fonte_id, client, minimo=1):
    fonte = sources.BY_ID[fonte_id]
    try:
        works = await fonte.search(client, fonte.render_query(STRATEGIA), 5, CONFIG, STRATEGIA.filtri)
    except httpx.HTTPStatusError as errore:
        _salta_se_limitata(errore, fonte_id)
    assert len(works) >= minimo, f"{fonte_id}: nessun risultato"
    primo = works[0]
    assert primo.title and primo.title != "(senza titolo)", f"{fonte_id}: titolo perso"
    assert primo.sources == [fonte_id]
    return works


async def test_openalex_risponde_e_i_campi_ci_sono(client):
    works = await _controlla("openalex", client)
    assert any(w.year for w in works), "OpenAlex: nessun anno"
    assert any(w.authors for w in works), "OpenAlex: nessun autore"


async def test_crossref_risponde_e_i_campi_ci_sono(client):
    works = await _controlla("crossref", client)
    assert any(w.doi for w in works), "Crossref: nessun DOI"


async def test_pubmed_risponde_e_i_campi_ci_sono(client):
    works = await _controlla("pubmed", client)
    assert all(w.url and "pubmed" in w.url for w in works)


async def test_europepmc_risponde_e_i_campi_ci_sono(client):
    works = await _controlla("europepmc", client)
    assert any(w.year for w in works)


async def test_arxiv_risponde_e_i_campi_ci_sono(client):
    works = await _controlla("arxiv", client)
    assert all(w.venue == "arXiv" for w in works)


async def test_doaj_risponde_e_i_campi_ci_sono(client):
    await _controlla("doaj", client)


async def test_openalex_estrae_ancora_i_concetti(client):
    try:
        concetti = await keywords._openalex_concepts("AI literacy in teacher education", client, CONFIG)
    except httpx.HTTPStatusError as errore:
        _salta_se_limitata(errore, "openalex")
    assert concetti and all(isinstance(nome, str) for nome, _ in concetti)


async def test_pubmed_traduce_ancora_in_mesh(client):
    try:
        termini = await keywords._pubmed_mesh("artificial intelligence literacy", client, CONFIG)
    except httpx.HTTPStatusError as errore:
        _salta_se_limitata(errore, "pubmed")
    assert termini, "PubMed non restituisce piu' i termini MeSH"


@pytest.mark.parametrize("etichetta", sorted({
    modello.nome
    for memoria in (4, 12, 24, 64, None)
    for silicio in (True, False)
    for modello in __import__("ricerca.macchina", fromlist=["macchina"]).consiglio(
        memoria=memoria, silicio_apple=silicio
    )
}))
async def test_i_modelli_consigliati_esistono_ancora(client, etichetta):
    """I nomi cambiano: un `ollama pull` che fallisce è un consiglio sbagliato."""

    nome, _, versione = etichetta.partition(":")
    risposta = await client.get(
        f"https://registry.ollama.ai/v2/library/{nome}/manifests/{versione or 'latest'}",
        headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
    )
    assert risposta.status_code == 200, f"{etichetta} non è più nel registro di Ollama"
