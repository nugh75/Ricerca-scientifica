import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import history, pdf, search
from ricerca.app import app
from ricerca.models import Block, SourceResult, Strategy, Work

client = TestClient(app)
PDF_FINTO = b"%PDF-1.7\n%%EOF\n"


def ricerca_salvata(quanti=4, oa=True):
    works = [
        Work(title=f"Studio {n}", year=2024, doi=f"10.1/{n}", sources=["openalex"],
             oa_url=f"https://esempio.org/{n}.pdf" if oa else None)
        for n in range(quanti)
    ]
    risultati = [SourceResult("openalex", "OpenAlex", "query esatta", works=works, secondi=0.4)]
    return history.salva("AI literacy", Strategy([Block("C", ["ai"])]), risultati, works)


def test_le_statistiche_dicono_quanto_porta_ogni_fonte():
    comune = Work(title="Comune", doi="10.1/c", sources=["openalex", "doaj"])
    solo_openalex = Work(title="Solo OpenAlex", doi="10.1/o", sources=["openalex"])
    righe = search.statistiche(
        [
            SourceResult("openalex", "OpenAlex", "q1", works=[comune, solo_openalex], secondi=0.5),
            SourceResult("doaj", "DOAJ", "q2", works=[comune], secondi=1.2),
        ],
        [comune, solo_openalex],
    )
    openalex, doaj = righe
    assert (openalex["trovati"], openalex["nel_totale"], openalex["soltanto"]) == (2, 2, 1)
    assert (doaj["trovati"], doaj["nel_totale"], doaj["soltanto"]) == (1, 1, 0)
    assert doaj["secondi"] == 1.2
    assert openalex["query"] == "q1"


def test_la_cronologia_conserva_query_e_statistiche():
    id_ricerca = ricerca_salvata()
    fonte = history.voce(id_ricerca)["fonti"][0]
    assert fonte["query"] == "query esatta"
    assert fonte["soltanto"] == 4
    assert fonte["secondi"] == 0.4


def test_il_pannello_mostra_la_query_inviata():
    id_ricerca = ricerca_salvata()
    pagina = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"})
    assert "query esatta" in pagina.text
    assert "Only here" in pagina.text


def test_inclusione_in_blocco_sui_soli_spuntati():
    id_ricerca = ricerca_salvata()
    client.post(f"/screening-massa/{id_ricerca}", data={"stato": "escluso", "selezione": [0, 2]})
    decisioni = [w.decisione for w in history.record(id_ricerca)]
    assert decisioni == ["escluso", "", "escluso", ""]


def test_il_comando_in_blocco_non_annulla_chi_e_gia_nello_stato():
    id_ricerca = ricerca_salvata()
    history.decide(id_ricerca, 0, "incluso", "già valutato")
    client.post(f"/screening-massa/{id_ricerca}", data={"stato": "incluso", "selezione": [0, 1]})
    record = history.record(id_ricerca)
    assert record[0].decisione == "incluso"
    assert record[0].motivo == "già valutato"
    assert record[1].decisione == "incluso"


def test_senza_selezione_nessuna_decisione_cambia():
    id_ricerca = ricerca_salvata()
    client.post(f"/screening-massa/{id_ricerca}", data={"stato": "escluso"})
    assert all(w.decisione == "" for w in history.record(id_ricerca))


@respx.mock
def test_scaricamento_dei_pdf_in_blocco():
    respx.get(url__startswith="https://esempio.org/").mock(
        return_value=httpx.Response(200, content=PDF_FINTO))
    id_ricerca = ricerca_salvata(quanti=3)

    pagina = client.post(f"/pdf-massa/{id_ricerca}", data={"selezione": [0, 1]})

    assert "PDFs downloaded: 2" in pagina.text
    record = history.record(id_ricerca)
    assert pdf.gia_scaricato(record[0]) and pdf.gia_scaricato(record[1])
    assert pdf.gia_scaricato(record[2]) is None


@respx.mock
def test_senza_spunte_scarica_tutto_e_conta_i_falliti():
    respx.get("https://esempio.org/0.pdf").mock(return_value=httpx.Response(200, content=PDF_FINTO))
    respx.get("https://esempio.org/1.pdf").mock(return_value=httpx.Response(403))
    id_ricerca = ricerca_salvata(quanti=2)

    pagina = client.post(f"/pdf-massa/{id_ricerca}", data={})

    assert "PDFs downloaded: 1" in pagina.text
    assert "failed: 1" in pagina.text


def test_i_record_senza_pdf_aperto_non_contano():
    id_ricerca = ricerca_salvata(quanti=2, oa=False)
    pagina = client.post(f"/pdf-massa/{id_ricerca}", data={})
    assert "PDFs downloaded: 0 · failed: 0" in pagina.text


def test_il_pannello_dei_campi_non_si_duplica():
    id_ricerca = ricerca_salvata()
    frammento = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text
    assert frammento.count("FIELDS TO SHOW AND EXPORT") <= 1
    assert frammento.count('id="campi-') == 1
