import httpx
import pytest
import respx

from ricerca import pdf
from ricerca.models import Work

PDF_FINTO = b"%PDF-1.7\n%%EOF\n"


def articolo(oa="https://esempio.org/f.pdf"):
    return Work(title="AI literacy", authors=["Duri Long"], year=2020, doi="10.1/x", oa_url=oa)


@respx.mock
async def test_scarica_salva_il_file_e_lo_ritrova():
    respx.get("https://esempio.org/f.pdf").mock(return_value=httpx.Response(200, content=PDF_FINTO))
    lavoro = articolo()
    assert pdf.gia_scaricato(lavoro) is None

    async with httpx.AsyncClient() as client:
        percorso = await pdf.scarica(lavoro, client)

    assert percorso.read_bytes() == PDF_FINTO
    assert percorso.name == "2020_long_ai-literacy.pdf"
    assert pdf.gia_scaricato(lavoro) == percorso


@respx.mock
async def test_un_secondo_scaricamento_non_richiama_la_rete():
    rotta = respx.get("https://esempio.org/f.pdf").mock(
        return_value=httpx.Response(200, content=PDF_FINTO)
    )
    async with httpx.AsyncClient() as client:
        await pdf.scarica(articolo(), client)
        await pdf.scarica(articolo(), client)
    assert rotta.call_count == 1


@respx.mock
async def test_una_pagina_html_non_viene_salvata_come_pdf():
    respx.get("https://esempio.org/f.pdf").mock(
        return_value=httpx.Response(200, content=b"<html>paywall</html>")
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await pdf.scarica(articolo(), client)
    assert pdf.gia_scaricato(articolo()) is None


async def test_senza_link_aperto_non_si_scarica_nulla():
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await pdf.scarica(articolo(oa=None), client)


@respx.mock
async def test_due_lavori_omonimi_non_si_sovrascrivono():
    """Stesso anno, stesso autore, stesso titolo, DOI diversi: due file."""

    respx.get(url__startswith="https://esempio.org/").mock(
        return_value=httpx.Response(200, content=PDF_FINTO))
    uno = Work(title="Stesso titolo", authors=["Rossi M"], year=2020, doi="10.1/a",
               oa_url="https://esempio.org/a.pdf")
    due = Work(title="Stesso titolo", authors=["Rossi M"], year=2020, doi="10.1/b",
               oa_url="https://esempio.org/b.pdf")

    async with httpx.AsyncClient() as client:
        primo = await pdf.scarica(uno, client)
        secondo = await pdf.scarica(due, client)

    assert primo.name == "2020_rossi_stesso-titolo.pdf"
    assert secondo.name == "2020_rossi_stesso-titolo-2.pdf"
    assert pdf.gia_scaricato(uno) == primo
    assert pdf.gia_scaricato(due) == secondo


@respx.mock
async def test_si_provano_tutti_i_collegamenti_finche_uno_da_un_pdf():
    """La prima strada è spesso una pagina di destinazione, non il file."""

    respx.get("https://esempio.org/pagina").mock(
        return_value=httpx.Response(200, content=b"<html>landing page</html>"))
    respx.get("https://esempio.org/rotto").mock(return_value=httpx.Response(403))
    respx.get("https://esempio.org/vero.pdf").mock(return_value=httpx.Response(200, content=PDF_FINTO))

    lavoro = Work(title="Studio", doi="10.1/x", year=2024, authors=["Rossi M"],
                  oa_url="https://esempio.org/pagina",
                  oa_urls=["https://esempio.org/rotto", "https://esempio.org/vero.pdf"])

    async with httpx.AsyncClient() as client:
        percorso = await pdf.scarica(lavoro, client)

    assert percorso.read_bytes() == PDF_FINTO


@respx.mock
async def test_se_nessun_collegamento_da_un_pdf_lo_dice_con_quanti_ne_ha_provati():
    respx.get(url__startswith="https://esempio.org/").mock(
        return_value=httpx.Response(200, content=b"<html>no</html>"))
    lavoro = Work(title="Studio", oa_url="https://esempio.org/a",
                  oa_urls=["https://esempio.org/b"])

    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="2 collegamenti"):
            await pdf.scarica(lavoro, client)


def test_i_candidati_non_si_ripetono():
    lavoro = Work(title="x", oa_url="https://a", oa_urls=["https://a", "https://b", ""])
    assert lavoro.candidati_pdf() == ["https://a", "https://b"]
