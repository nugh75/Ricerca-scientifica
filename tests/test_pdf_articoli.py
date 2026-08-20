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

    client.post(f"/pdf-massa/{id_ricerca}", data={"tutti": "1"})
    dopo = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text
    assert f"/pdf/{id_ricerca}.zip" in dopo
    assert "3 on disk" in dopo


@respx.mock
def test_il_nome_dentro_lo_zip_e_leggibile():
    respx.get("https://esempio.org/0.pdf").mock(return_value=httpx.Response(200, content=PDF_FINTO))
    id_ricerca = ricerca_con_pdf(quanti=1)
    client.post(f"/pdf-massa/{id_ricerca}", data={"tutti": "1"})

    with zipfile.ZipFile(io.BytesIO(client.get(f"/pdf/{id_ricerca}.zip").content)) as archivio:
        assert archivio.namelist()[0] == "2024_rossi_studio-0.pdf"


@respx.mock
def test_il_pdf_viene_servito_per_essere_letto_non_scaricato():
    respx.get(url__startswith="https://esempio.org/").mock(
        return_value=httpx.Response(200, content=PDF_FINTO))
    id_ricerca = ricerca_con_pdf(quanti=1)
    client.post(f"/pdf-massa/{id_ricerca}", data={"tutti": "1"})

    risposta = client.get(f"/pdf/{id_ricerca}/0/file")

    assert risposta.headers["content-type"] == "application/pdf"
    assert risposta.headers["content-disposition"].startswith("inline")


@respx.mock
def test_il_tasto_apre_il_lettore_interno_non_una_finestra_esterna():
    respx.get(url__startswith="https://esempio.org/").mock(
        return_value=httpx.Response(200, content=PDF_FINTO))
    id_ricerca = ricerca_con_pdf(quanti=1)
    client.post(f"/pdf-massa/{id_ricerca}", data={"tutti": "1"})

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


def test_il_nome_del_file_e_anno_autori_titolo():
    nome = pdf.nome_file(Work(
        title="Teaching Students to Question the Machine",
        authors=["Olivier Clerc", "Rania Abdelghani"], year=2026,
    ))
    assert nome == "2026_clerc-abdelghani_teaching-students-to-question-the-machine.pdf"


def test_oltre_tre_autori_si_abbrevia():
    nome = pdf.nome_file(Work(title="Studio", year=2024,
                              authors=["Rossi M", "Bianchi L", "Verdi G", "Neri P"]))
    assert nome.startswith("2024_rossi-bianchi-verdi-et-al_studio")


def test_accenti_e_apostrofi_non_finiscono_nel_nome():
    nome = pdf.nome_file(Work(title="Perché l'IA è in classe", authors=["Rossi M"], year=2024))
    assert nome == "2024_rossi_perche-l-ia-e-in-classe.pdf"
    assert all(carattere.isascii() for carattere in nome)


def test_senza_anno_e_senza_autori_il_nome_regge():
    assert pdf.nome_file(Work(title="Senza dati")) == "sd_anon_senza-dati.pdf"


@respx.mock
async def test_un_pdf_scaricato_col_vecchio_nome_viene_rinominato():
    lavoro = Work(title="AI literacy", authors=["Duri Long"], year=2020,
                  doi="10.1/x", oa_url="https://esempio.org/f.pdf")
    vecchio = pdf.cartella() / pdf._nome_storico(lavoro)
    vecchio.write_bytes(PDF_FINTO)
    (vecchio.with_suffix(".txt")).write_text("testo estratto")

    trovato = pdf.gia_scaricato(lavoro)

    assert trovato.name == "2020_long_ai-literacy.pdf"
    assert trovato.read_bytes() == PDF_FINTO
    assert trovato.with_suffix(".txt").read_text() == "testo estratto"
    assert not vecchio.exists()          # niente doppioni


def test_le_impostazioni_dicono_dove_stanno_i_pdf():
    pagina = client.get("/impostazioni").text
    assert "PDF folder" in pagina
    assert "/pdf" in pagina
    assert "named year_authors_title" in pagina
