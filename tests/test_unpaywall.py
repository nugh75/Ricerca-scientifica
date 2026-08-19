import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from ricerca import config as config_module
from ricerca import history, unpaywall
from ricerca.app import app
from ricerca.config import Config
from ricerca.models import Block, SourceResult, Strategy, Work

client = TestClient(app)

RISPOSTA = {
    "title": "AI literacy and teaching",
    "journal_name": "Computers in Human Behavior",
    "year": 2023,
    "publisher": "Elsevier BV",
    "oa_status": "green",
    "z_authors": [
        {"raw_author_name": "Sadia Chowdhury"},
        {"given": "Maria", "family": "Alvarez"},
    ],
    "best_oa_location": {"url_for_pdf": "https://pmc.esempio/main.pdf", "version": "submittedVersion"},
}


def ricerca_incompleta():
    works = [
        Work(title="Studio senza dati", doi="10.1016/j.chb.2023.107799", sources=["crossref"]),
        Work(title="Studio completo", doi="10.1/completo", year=2024, venue="Rivista",
             authors=["Rossi M"], oa_url="https://esempio/x.pdf", sources=["doaj"]),
    ]
    return history.salva("t", Strategy([Block("C", ["x"])]),
                         [SourceResult("crossref", "Crossref", "q", works=works)], works)


async def test_senza_email_non_si_interroga():
    with pytest.raises(unpaywall.SenzaEmail):
        await unpaywall.dati("10.1/x", Config(), httpx.AsyncClient())


@respx.mock
async def test_legge_sede_anno_autori_e_pdf_aperto():
    rotta = respx.get(url__startswith=f"{unpaywall.API}/10.1016/j.chb.2023.107799").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    dati = await unpaywall.dati(
        "https://doi.org/10.1016/j.chb.2023.107799",
        Config(mailto="x@y.it"),
        httpx.AsyncClient(),
    )

    assert dati["venue"] == "Computers in Human Behavior"
    assert dati["year"] == 2023
    assert dati["authors"] == ["Sadia Chowdhury", "Maria Alvarez"]   # due formati di nome
    assert dati["oa_url"] == "https://pmc.esempio/main.pdf"
    assert "email=x%40y.it" in str(rotta.calls[0].request.url)


@respx.mock
async def test_un_doi_sconosciuto_non_e_un_errore():
    respx.get(url__startswith=unpaywall.API).mock(return_value=httpx.Response(404))
    assert await unpaywall.dati("10.1/mai-visto", Config(mailto="x@y.it"), httpx.AsyncClient()) == {}


def test_si_completa_solo_cio_che_manca():
    pieno = Work(title="x", doi="10.1/x", year=2024, venue="Rivista",
                 authors=["Rossi M"], oa_url="https://esempio/x.pdf")
    assert unpaywall.da_completare(pieno) == []
    aggiunte = unpaywall.completamento(pieno, {"venue": "Altra rivista", "year": 1999})
    assert aggiunte == {}          # quel che c'è non si tocca

    vuoto = Work(title="x", doi="10.1/x")
    assert unpaywall.completamento(vuoto, {"venue": "Rivista", "year": 2023}) == {
        "venue": "Rivista", "year": 2023
    }


@respx.mock
def test_il_comando_in_blocco_completa_i_record_incompleti():
    config_module.save(Config(mailto="x@y.it", configurato="1"))
    respx.get(url__startswith=unpaywall.API).mock(return_value=httpx.Response(200, json=RISPOSTA))
    id_ricerca = ricerca_incompleta()

    pagina = client.post(f"/unpaywall/{id_ricerca}", data={})

    assert "Filled in from Unpaywall: 1" in pagina.text
    record = history.record(id_ricerca)
    assert record[0].venue == "Computers in Human Behavior"
    assert record[0].oa_url == "https://pmc.esempio/main.pdf"
    assert set(record[0].completato) >= {"venue", "year", "oa_url", "authors"}
    # il record che era già completo non è stato toccato
    assert record[1].venue == "Rivista" and record[1].completato == []


def test_senza_email_il_comando_lo_dice_invece_di_tacere():
    config_module.save(Config(configurato="1"))
    id_ricerca = ricerca_incompleta()
    pagina = client.post(f"/unpaywall/{id_ricerca}", data={})
    assert "needs the courtesy email" in pagina.text


@respx.mock
def test_la_correzione_a_mano_vince_sul_completamento():
    config_module.save(Config(mailto="x@y.it", configurato="1"))
    respx.get(url__startswith=unpaywall.API).mock(return_value=httpx.Response(200, json=RISPOSTA))
    id_ricerca = ricerca_incompleta()

    client.post(f"/unpaywall/{id_ricerca}", data={})
    client.post(f"/scheda/{id_ricerca}/0", data={"year": "2019"})

    record = history.record(id_ricerca)[0]
    assert record.year == 2019
    assert "year" in record.corretto and "year" not in record.completato


@respx.mock
def test_dalla_scheda_si_completa_un_record_solo():
    config_module.save(Config(mailto="x@y.it", configurato="1"))
    respx.get(url__startswith=unpaywall.API).mock(return_value=httpx.Response(200, json=RISPOSTA))
    id_ricerca = ricerca_incompleta()

    scheda = client.post(f"/scheda/{id_ricerca}/0/unpaywall").text

    assert "Computers in Human Behavior" in scheda
    assert "from Unpaywall" in scheda
    assert history.record(id_ricerca)[1].completato == []   # solo quello aperto


@respx.mock
def test_un_guasto_di_unpaywall_finisce_nel_registro():
    from ricerca import registro

    config_module.save(Config(mailto="x@y.it", configurato="1"))
    registro.svuota()
    respx.get(url__startswith=unpaywall.API).mock(return_value=httpx.Response(503))
    id_ricerca = ricerca_incompleta()

    pagina = client.post(f"/unpaywall/{id_ricerca}", data={})

    assert "failed: 1" in pagina.text
    assert any("Unpaywall" in v.azione for v in registro.ultime())
