import re
from pathlib import Path

import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import config as config_module
from ricerca import history, macchina, search
from ricerca.app import PER_PAGINA, app
from ricerca.config import Config
from ricerca.models import Block, SourceResult, Strategy, Work

client = TestClient(app)
RADICE = Path(__file__).resolve().parent.parent
FOGLIO = (RADICE / "ricerca/static/style.css").read_text()


def ricerca_con(quanti):
    works = [Work(title=f"Studio {n}", year=2024, doi=f"10.1/{n}", sources=["openalex"])
             for n in range(quanti)]
    return history.salva("t", Strategy([Block("C", ["x"])]),
                         [SourceResult("openalex", "OpenAlex", "q", works=works)], works)


# ── schermi ───────────────────────────────────────────────────────────
def test_le_tabelle_scorrono_dentro_il_loro_riquadro():
    id_ricerca = ricerca_con(3)
    pagina = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text
    assert '<div class="scorre">' in pagina
    assert ".scorre { overflow-x: auto;" in FOGLIO


def test_sotto_i_768_le_righe_diventano_schede():
    assert "@media (max-width: 48rem)" in FOGLIO
    blocco = FOGLIO[FOGLIO.index("@media (max-width: 48rem)"):]
    assert "table.risultati thead { display: none; }" in blocco
    assert "td[data-etichetta]::before" in blocco

    id_ricerca = ricerca_con(2)
    pagina = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text
    assert 'data-etichetta=' in pagina          # ogni cella dice che cosa contiene


def test_sugli_schermi_larghi_il_contenuto_si_allarga():
    assert "max-width: min(96vw, 1680px)" in FOGLIO
    # il testo resta comunque leggibile
    assert "max-width: 72ch" in FOGLIO


def test_la_densita_si_sceglie_e_resta():
    client.post("/densita/compatta")
    assert config_module.load().densita == "compatta"
    assert 'data-densita="compatta"' in client.get("/impostazioni").text
    client.post("/densita/comoda")
    assert 'data-densita="comoda"' in client.get("/impostazioni").text
    assert 'html[data-densita="compatta"]' in FOGLIO


def test_i_comandi_restano_a_portata():
    assert "form.comandi {\n  position: sticky;" in FOGLIO


def test_una_ricerca_salvata_separa_risultati_e_protocollo():
    id_ricerca = ricerca_con(3)
    pagina = client.get(f"/cronologia/{id_ricerca}").text

    assert 'role="tablist"' in pagina
    assert 'id="tab-risultati"' in pagina and 'aria-selected="true"' in pagina
    assert 'id="tab-protocollo"' in pagina and 'aria-selected="false"' in pagina
    assert 'id="pannello-protocollo"' in pagina and "hidden" in pagina
    assert pagina.count('class="fonti-statistiche"') == 1


def test_i_comandi_compatti_hanno_icona_e_tooltip_accessibile():
    pagina = client.get("/").text

    assert 'class="icona"' in pagina
    assert 'class="lingua solo-icona tooltip' in pagina
    assert 'aria-label="roomy"' in pagina
    assert 'data-tooltip="roomy"' in pagina


def test_gli_avvisi_non_hanno_la_barra_verticale():
    blocco = FOGLIO[FOGLIO.index(".avviso {"):FOGLIO.index(".chiudi-avviso {")]
    assert "border-left" not in blocco


# ── macchine ──────────────────────────────────────────────────────────
def test_l_elenco_e_diviso_in_pagine():
    id_ricerca = ricerca_con(PER_PAGINA + 20)

    prima = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text
    assert prima.count('tabindex="0" data-riga=') == PER_PAGINA
    assert "page 1 of 2" in prima

    seconda = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella", "pagina": "2"}).text
    assert seconda.count('tabindex="0" data-riga=') == 20
    assert 'data-riga="50"' in seconda          # gli indici restano assoluti


def test_una_pagina_inesistente_ricade_sull_ultima():
    id_ricerca = ricerca_con(10)
    pagina = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella", "pagina": "99"}).text
    assert 'data-riga="0"' in pagina


def test_lo_screening_dalla_seconda_pagina_colpisce_il_record_giusto():
    id_ricerca = ricerca_con(PER_PAGINA + 5)
    client.post(f"/screening/{id_ricerca}/52", data={"stato": "incluso", "motivo": ""})
    record = history.record(id_ricerca)
    assert record[52].decisione == "incluso"
    assert record[2].decisione == ""


def test_il_carattere_e_nel_pacchetto_non_in_rete():
    assert "@font-face" in FOGLIO
    assert "/static/font/jetbrains-mono-400-latin.woff2" in FOGLIO
    base = (RADICE / "ricerca/templates/base.html").read_text()
    assert "fonts.googleapis.com" not in base
    assert (RADICE / "ricerca/static/font/jetbrains-mono-400-latin.woff2").exists()


def test_il_limite_predefinito_segue_la_memoria():
    assert macchina.limite_consigliato(memoria=4) == 15
    assert macchina.limite_consigliato(memoria=12) == 25
    assert macchina.limite_consigliato(memoria=64) == 50
    assert macchina.limite_consigliato(memoria=None) == 25


@respx.mock
async def test_senza_rete_un_solo_messaggio():
    for indirizzo in ("https://api.openalex.org", "https://api.crossref.org", "https://doaj.org"):
        respx.get(url__startswith=indirizzo).mock(side_effect=httpx.ConnectError("rete assente"))

    risultati, _ = await search.run(
        Strategy([Block("C", ["x"])]), ["openalex", "crossref", "doaj"], 5, Config()
    )

    messaggi = {r.error for r in risultati}
    assert len(messaggi) == 1
    assert "connection" in messaggi.pop()
    assert search.SENZA_RETE not in " ".join(r.error for r in risultati)


@respx.mock
async def test_una_sola_fonte_giu_non_diventa_un_allarme_di_rete():
    respx.get(url__startswith="https://api.openalex.org").mock(
        return_value=httpx.Response(200, json={"results": []}))
    respx.get(url__startswith="https://doaj.org").mock(side_effect=httpx.ConnectError("giù"))

    risultati, _ = await search.run(
        Strategy([Block("C", ["x"])]), ["openalex", "doaj"], 5, Config()
    )

    errori = [r.error for r in risultati if r.error]
    assert errori == ["unreachable"]


# ── uso ───────────────────────────────────────────────────────────────
def test_le_righe_sono_raggiungibili_da_tastiera():
    id_ricerca = ricerca_con(3)
    pagina = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text
    assert 'tabindex="0" data-riga="0"' in pagina
    assert "«i» includes" in pagina

    base = (RADICE / "ricerca/templates/base.html").read_text()
    assert "SCORCIATOIE" in base
    assert '"ArrowDown"' in base


@respx.mock
async def test_una_fonte_sola_irraggiungibile_non_diventa_un_allarme_di_rete():
    """Con una banca dati sola non si può dire che manchi internet."""

    respx.get(url__startswith="https://export.arxiv.org").mock(
        side_effect=httpx.ConnectError("giù"))

    risultati, _ = await search.run(Strategy([Block("C", ["x"])]), ["arxiv"], 5, Config())

    assert risultati[0].error == "unreachable"
    assert "connection" not in risultati[0].error


@respx.mock
async def test_il_marcatore_interno_non_finisce_nel_registro():
    from ricerca import registro

    registro.svuota()
    respx.get(url__startswith="https://export.arxiv.org").mock(
        side_effect=httpx.ConnectError("giù"))

    await search.run(Strategy([Block("C", ["x"])]), ["arxiv"], 5, Config())

    righe = " ".join(f"{v.azione} {v.dettaglio}" for v in registro.ultime())
    assert search.SENZA_RETE not in righe
    assert "unreachable" in righe
