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
