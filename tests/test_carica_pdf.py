import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from ricerca import biblioteca, history, pdf
from ricerca.app import app
from ricerca.models import Block, SourceResult, Strategy, Work

client = TestClient(app)
PDF_FINTO = b"%PDF-1.7\n%%EOF\n"


def ricerca_chiusa():
    """Un articolo senza copia aperta: l'editore lo dà solo a chi ha le credenziali."""

    works = [Work(title="Articolo dietro paywall", doi="10.1/chiuso", year=2024,
                  authors=["Rossi M"], sources=["crossref"])]
    return history.salva("t", Strategy([Block("C", ["x"])]),
                         [SourceResult("crossref", "Crossref", "q", works=works)], works)


def test_la_scheda_spiega_come_fare_quando_il_pdf_non_si_scarica():
    id_ricerca = ricerca_chiusa()
    scheda = client.get(f"/scheda/{id_ricerca}/0").text
    assert "block programs but not people" in scheda
    assert "institutional credentials" in scheda
    assert 'hx-post="/pdf/' in scheda and "carica" in scheda


def test_un_pdf_caricato_a_mano_entra_come_gli_altri():
    id_ricerca = ricerca_chiusa()

    risposta = client.post(
        f"/pdf/{id_ricerca}/0/carica",
        files={"file": ("scaricato-dal-browser.pdf", PDF_FINTO, "application/pdf")},
    )

    assert risposta.status_code == 200
    percorso = pdf.gia_scaricato(history.record(id_ricerca)[0])
    assert percorso is not None
    assert percorso.name == "2024_rossi_articolo-dietro-paywall.pdf"   # stesso schema di nomi
    assert percorso.read_bytes() == PDF_FINTO
    assert "open PDF" in risposta.text        # la scheda ora lo offre in lettura


def test_un_file_che_non_e_un_pdf_viene_rifiutato():
    from ricerca import registro

    registro.svuota()
    id_ricerca = ricerca_chiusa()

    client.post(f"/pdf/{id_ricerca}/0/carica",
                files={"file": ("finto.pdf", b"<html>pagina di login</html>", "application/pdf")})

    assert pdf.gia_scaricato(history.record(id_ricerca)[0]) is None
    assert any("PDF" in v.azione for v in registro.ultime() if v.errore)


def test_il_pdf_caricato_finisce_nella_ricerca_a_testo_pieno():
    id_ricerca = ricerca_chiusa()
    testo = b"%PDF-1.7\n"      # senza testo estraibile pypdf non trova nulla
    client.post(f"/pdf/{id_ricerca}/0/carica", files={"file": ("x.pdf", testo, "application/pdf")})
    percorso = pdf.gia_scaricato(history.record(id_ricerca)[0])
    assert percorso.parent == biblioteca.cartella()


def test_un_pdf_caricato_si_puo_riassumere():
    id_ricerca = ricerca_chiusa()
    client.post(f"/pdf/{id_ricerca}/0/carica", files={"file": ("x.pdf", PDF_FINTO, "application/pdf")})
    scheda = client.get(f"/scheda/{id_ricerca}/0").text
    assert "no text to summarise" not in scheda or "A model is needed" in scheda
