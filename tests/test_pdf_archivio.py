import httpx
import pytest
import respx

from ricerca import costo, pdf
from ricerca import config as config_module
from ricerca.config import Config
from ricerca.models import Work

PDF_FINTO = b"%PDF-1.4 finto"


def lavoro() -> Work:
    return Work(
        title="Un articolo", year=2024, doi="10.1/x",
        oa_url="https://editore/rotto.pdf",
        openalex_id="W42",
        pdf_archivio="https://content.openalex.org/works/W42.pdf",
    )


@respx.mock
async def test_l_archivio_si_prova_solo_dopo_gli_altri():
    config_module.save(Config(openalex_api_key="k", openalex_contenuti="1"))
    respx.get("https://editore/rotto.pdf").mock(return_value=httpx.Response(404))
    archivio = respx.get(url__startswith="https://content.openalex.org/works/W42.pdf").mock(
        return_value=httpx.Response(200, content=PDF_FINTO)
    )
    async with httpx.AsyncClient() as client:
        percorso = await pdf.scarica(lavoro(), client)
    assert percorso.read_bytes() == PDF_FINTO
    assert "api_key=k" in str(archivio.calls[0].request.url)
    assert costo.speso() == costo.COSTO_PDF


@respx.mock
async def test_se_il_collegamento_aperto_funziona_l_archivio_non_si_tocca():
    config_module.save(Config(openalex_api_key="k", openalex_contenuti="1"))
    respx.get("https://editore/rotto.pdf").mock(
        return_value=httpx.Response(200, content=PDF_FINTO)
    )
    archivio = respx.get(url__startswith="https://content.openalex.org").mock(
        return_value=httpx.Response(200, content=PDF_FINTO)
    )
    async with httpx.AsyncClient() as client:
        await pdf.scarica(lavoro(), client)
    assert not archivio.called
    assert costo.speso() == 0.0


@respx.mock
async def test_spento_di_suo_non_si_paga_niente():
    config_module.save(Config(openalex_api_key="k"))
    respx.get("https://editore/rotto.pdf").mock(return_value=httpx.Response(404))
    archivio = respx.get(url__startswith="https://content.openalex.org").mock(
        return_value=httpx.Response(200, content=PDF_FINTO)
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await pdf.scarica(lavoro(), client)
    assert not archivio.called


@respx.mock
async def test_senza_chiave_l_archivio_non_si_prova():
    config_module.save(Config(openalex_contenuti="1"))
    respx.get("https://editore/rotto.pdf").mock(return_value=httpx.Response(404))
    archivio = respx.get(url__startswith="https://content.openalex.org").mock(
        return_value=httpx.Response(401, json={"error": "API key required"})
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await pdf.scarica(lavoro(), client)
    assert not archivio.called
