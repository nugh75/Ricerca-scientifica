import re

import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import lavori, registro, watchdog
from ricerca.app import app

client = TestClient(app)
WORKS = {"results": [{"id": "https://openalex.org/W1", "title": "Uno", "publication_year": 2024,
                      "doi": "https://doi.org/10.1/x", "authorships": [], "primary_location": {}}]}


def test_il_registro_tiene_le_ultime_voci_e_conta_gli_errori():
    registro.svuota()
    registro.annota("ricerca", "OpenAlex 25 record")
    registro.errore("ricerca", "DOAJ: HTTP 503")

    ultime = registro.ultime()
    assert ultime[0].azione == "ricerca" and ultime[0].errore is True
    assert ultime[1].errore is False
    assert registro.quanti_errori() == 1


def test_il_registro_finisce_anche_su_file(isolated_config):
    registro.annota("prova", "riga da conservare")
    testo = (isolated_config / "activity.log").read_text(encoding="utf-8")
    assert "riga da conservare" in testo


def test_la_pagina_mostra_il_registro():
    registro.svuota()
    registro.errore("PDF non scaricato", "HTTP 403")
    pagina = client.get("/registro").text
    assert "PDF non scaricato" in pagina and "HTTP 403" in pagina
    assert "with errors" in pagina


def test_il_registro_si_svuota_e_si_scarica():
    registro.annota("qualcosa", "di passato")
    assert "qualcosa" in client.get("/registro.txt").text
    client.post("/registro/svuota")
    assert registro.ultime() == []


@respx.mock
def test_una_ricerca_lascia_traccia_di_ogni_fonte(esegui_ricerca):
    registro.svuota()
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=WORKS))
    respx.get(url__startswith="https://doaj.org").mock(return_value=httpx.Response(503))

    esegui_ricerca(client, {"label": ["C"], "terms": ["x"], "mesh": "",
                            "fonte": ["openalex", "doaj"], "limite": "5", "topic": "prova"})

    righe = " ".join(f"{v.azione} {v.dettaglio}" for v in registro.ultime())
    assert "OpenAlex: 1 records" in righe          # interfaccia in inglese
    assert "DOAJ" in righe and "503" in righe
    assert "search finished" in righe
    assert "1 raw records" in righe
    assert registro.quanti_errori() >= 1


@respx.mock
def test_il_registro_parla_la_lingua_dell_interfaccia(esegui_ricerca):
    from ricerca import config as config_module
    from ricerca.config import Config

    registro.svuota()
    config_module.save(Config(lang="it", configurato="1"))
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=WORKS))

    esegui_ricerca(client, {"label": ["C"], "terms": ["x"], "mesh": "",
                            "fonte": ["openalex"], "limite": "5", "topic": "prova"})

    righe = " ".join(f"{v.azione} {v.dettaglio}" for v in registro.ultime())
    assert "OpenAlex: 1 record" in righe
    assert "ricerca conclusa" in righe
    assert "record grezzi" in righe


def test_un_guasto_imprevisto_non_resta_muto():
    """Come in esercizio: l'errore non risale, viene raccolto e mostrato."""

    registro.svuota()

    @app.get("/rotta-di-prova")
    async def rotta_di_prova():
        raise RuntimeError("guasto voluto")

    cliente_come_in_esercizio = TestClient(app, raise_server_exceptions=False)
    risposta = cliente_come_in_esercizio.get("/rotta-di-prova", follow_redirects=False)

    assert risposta.status_code == 500
    assert "went wrong" in risposta.text
    righe = " ".join(f"{v.azione} {v.dettaglio}" for v in registro.ultime())
    assert "guasto voluto" in righe


@respx.mock
def test_la_ricerca_parte_in_background_e_si_puo_lasciare_la_pagina():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=WORKS))

    risposta = client.post("/cerca", data={"label": ["C"], "terms": ["x"], "mesh": "",
                                           "fonte": ["openalex"], "limite": "5", "topic": "in background"})

    assert "Running" in risposta.text          # la pagina non aspetta
    assert "/lavoro/" in risposta.text
    id_lavoro = re.search(r"/lavoro/([A-Za-z0-9_-]+)", risposta.text).group(1)

    client.get("/cronologia")                  # l'utente cambia pagina
    lavoro = lavori.attendi(id_lavoro, timeout=30)

    assert lavoro.stato == "finito"            # il lavoro è andato avanti lo stesso
    assert "Uno" in client.get(f"/lavoro/{id_lavoro}").text


def test_un_lavoro_fallito_lo_dice_invece_di_sparire():
    async def rotto():
        raise ValueError("banca dati irraggiungibile")

    lavoro = lavori.avvia(rotto(), "prova che fallisce")
    lavori.attendi(lavoro.id, timeout=10)

    pagina = client.get(f"/lavoro/{lavoro.id}").text
    assert "Did not finish" in pagina
    assert "banca dati irraggiungibile" in pagina


def test_l_app_non_si_spegne_mentre_lavora():
    stato = watchdog.Sorveglianza()
    stato.battito()
    lontano = stato.ultimo_battito + watchdog.SILENZIO_MASSIMO + 10

    stato.lavori_in_corso = lambda: 1
    assert stato.deve_fermarsi(lontano) is False      # c'è un lavoro in corso

    stato.lavori_in_corso = lambda: 0
    stato.apre_una_richiesta()
    assert stato.deve_fermarsi(lontano) is False      # c'è una richiesta aperta

    stato.chiude_una_richiesta()
    assert stato.deve_fermarsi(lontano + 100) is True  # ora può spegnersi


def test_il_silenzio_tollerato_regge_le_finestre_in_secondo_piano():
    """I browser rallentano i timer a un battito al minuto."""

    assert watchdog.SILENZIO_MASSIMO >= 70


def test_l_attesa_punta_sempre_al_contenitore_giusto():
    """Un bersaglio vuoto faceva ripiegare htmx sull'elemento stesso, e ogni
    giro di attesa annidava una copia dentro la precedente."""

    async def lento():
        import asyncio

        await asyncio.sleep(5)

    lavoro = lavori.avvia(lento(), "prova lenta")
    frammento = client.get(f"/lavoro/{lavoro.id}").text

    assert 'hx-target="#passo-tre"' in frammento
    assert 'hx-target=""' not in frammento
    assert "bersaglio" not in frammento          # niente selettori nell'indirizzo
    assert frammento.count('class="passo entra"') == 1
    assert "data-passo" not in frammento


def test_l_attesa_non_si_annida_a_ogni_giro():
    async def lento():
        import asyncio

        await asyncio.sleep(5)

    lavoro = lavori.avvia(lento(), "prova lenta")
    for _ in range(3):
        frammento = client.get(f"/lavoro/{lavoro.id}").text
        assert frammento.count("<section") == 1


@respx.mock
def test_i_risultati_prendono_l_indirizzo_della_ricerca_salvata():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=WORKS))

    risposta = client.post("/cerca", data={"label": ["C"], "terms": ["x"], "mesh": "",
                                           "fonte": ["openalex"], "limite": "5", "topic": "indirizzo"})
    id_lavoro = re.search(r"/lavoro/([A-Za-z0-9_-]+)", risposta.text).group(1)
    lavoro = lavori.attendi(id_lavoro, timeout=30)

    finita = client.get(f"/lavoro/{id_lavoro}")

    assert finita.headers["HX-Push-Url"] == f"/cronologia/{lavoro.risultato}"
    # E quell'indirizzo apre davvero la ricerca, ricaricando la pagina.
    assert "indirizzo" in client.get(f"/cronologia/{lavoro.risultato}").text
