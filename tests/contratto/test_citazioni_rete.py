import httpx
import pytest

from ricerca import citazioni
from ricerca.config import Config
from ricerca.models import Work

pytestmark = pytest.mark.rete


async def test_le_tre_direzioni_rispondono_davvero():
    seme = Work(title="Semantic Scholar", openalex_id="W2741809807")
    async with httpx.AsyncClient() as client:
        for verso in citazioni.VERSI:
            trovati = await citazioni.cerca(seme, verso, Config(), client, limite=5)
            assert trovati, f"nessun risultato per {verso}"


async def test_un_record_pubmed_si_collega_davvero_a_openalex_dal_doi():
    seme = Work(
        title="Nurse educators' experiences and perceptions using generative artificial intelligence",
        doi="10.1186/s12909-026-10113-0",
        sources=["pubmed", "europepmc"],
    )
    async with httpx.AsyncClient() as client:
        risolto = await citazioni.risolvi(seme, Config(), client)

    assert risolto.openalex_id == "W7203561228"
    assert risolto.doi == "https://doi.org/10.1186/s12909-026-10113-0"
