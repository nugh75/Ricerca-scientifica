import io
import zipfile

import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import history, pdf
from ricerca.app import app
from ricerca.models import Block, SourceResult, Strategy, Work

client = TestClient(app)
PDF_FINTO = b"%PDF-1.7\n%%EOF\n"


def ricerca_con_pdf(quanti=3):
    works = [
        Work(title=f"Studio {n}", year=2024, doi=f"10.1/{n}", authors=["Rossi M"],
             sources=["openalex"], oa_url=f"https://esempio.org/{n}.pdf")
        for n in range(quanti)
    ]
    return history.salva("t", Strategy([Block("C", ["x"])]),
                         [SourceResult("openalex", "OpenAlex", "q", works=works)], works)


def test_la_colonna_pdf_c_e_anche_senza_spuntare_il_campo():
    id_ricerca = ricerca_con_pdf()
    pagina = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text
    assert "download PDF" in pagina           # il tasto per riga
    assert f"/pdf/{id_ricerca}/0" in pagina


@respx.mock
def test_lo_zip_raccoglie_i_pdf_scaricati():
    respx.get(url__startswith="https://esempio.org/").mock(
        return_value=httpx.Response(200, content=PDF_FINTO))
    id_ricerca = ricerca_con_pdf()
    client.post(f"/pdf-massa/{id_ricerca}", data={"selezione": [0, 1]})

    risposta = client.get(f"/pdf/{id_ricerca}.zip")

    assert risposta.status_code == 200
    assert risposta.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(risposta.content)) as archivio:
        nomi = archivio.namelist()
        assert len(nomi) == 2
        assert all(nome.endswith(".pdf") for nome in nomi)
        assert archivio.read(nomi[0]) == PDF_FINTO


def test_lo_zip_vuoto_spiega_che_cosa_fare():
    id_ricerca = ricerca_con_pdf()
    risposta = client.get(f"/pdf/{id_ricerca}.zip")
    assert risposta.status_code == 404
    assert "download open PDFs" in risposta.text


@respx.mock
def test_il_tasto_zip_compare_solo_con_i_pdf_sul_disco():
    respx.get(url__startswith="https://esempio.org/").mock(
        return_value=httpx.Response(200, content=PDF_FINTO))
    id_ricerca = ricerca_con_pdf()

    prima = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text
    assert f"/pdf/{id_ricerca}.zip" not in prima

    client.post(f"/pdf-massa/{id_ricerca}", data={})
    dopo = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text
    assert f"/pdf/{id_ricerca}.zip" in dopo
    assert "3 on disk" in dopo


@respx.mock
def test_il_nome_dentro_lo_zip_e_la_chiave_di_citazione():
    respx.get("https://esempio.org/0.pdf").mock(return_value=httpx.Response(200, content=PDF_FINTO))
    id_ricerca = ricerca_con_pdf(quanti=1)
    client.post(f"/pdf-massa/{id_ricerca}", data={})

    with zipfile.ZipFile(io.BytesIO(client.get(f"/pdf/{id_ricerca}.zip").content)) as archivio:
        assert archivio.namelist()[0].startswith("rossi2024studio")


@respx.mock
def test_il_pdf_viene_servito_per_essere_letto_non_scaricato():
    respx.get(url__startswith="https://esempio.org/").mock(
        return_value=httpx.Response(200, content=PDF_FINTO))
    id_ricerca = ricerca_con_pdf(quanti=1)
    client.post(f"/pdf-massa/{id_ricerca}", data={})

    risposta = client.get(f"/pdf/{id_ricerca}/0/file")

    assert risposta.headers["content-type"] == "application/pdf"
    assert risposta.headers["content-disposition"].startswith("inline")


@respx.mock
def test_il_tasto_apre_il_lettore_interno_non_una_finestra_esterna():
    respx.get(url__startswith="https://esempio.org/").mock(
        return_value=httpx.Response(200, content=PDF_FINTO))
    id_ricerca = ricerca_con_pdf(quanti=1)
    client.post(f"/pdf-massa/{id_ricerca}", data={})

    cella = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text

    assert f'data-pdf="/pdf/{id_ricerca}/0/file"' in cella
    assert 'target="_blank"' not in cella.split("SCREENING")[-1][:600]


def test_il_lettore_esiste_in_ogni_pagina():
    for indirizzo in ("/", "/cronologia", "/biblioteca", "/impostazioni"):
        pagina = client.get(indirizzo, follow_redirects=True).text
        assert '<dialog id="lettore"' in pagina, indirizzo
        assert 'id="lettore-telaio"' in pagina, indirizzo


def test_il_lettore_offre_comunque_la_via_d_uscita():
    """Se un browser non sa mostrare i PDF, resta il modo di aprirlo fuori."""

    pagina = client.get("/", follow_redirects=True).text
    assert 'id="lettore-fuori"' in pagina
    assert "open outside the app" in pagina
