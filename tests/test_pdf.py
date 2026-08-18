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
    assert percorso.name.startswith("long2020ai")
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


def test_il_nome_del_file_distingue_record_diversi():
    uno = pdf.nome_file(Work(title="Stesso titolo", authors=["Rossi M"], year=2020, doi="10.1/a"))
    due = pdf.nome_file(Work(title="Stesso titolo", authors=["Rossi M"], year=2020, doi="10.1/b"))
    assert uno != due
