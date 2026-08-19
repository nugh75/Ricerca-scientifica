import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from ricerca import config as config_module
from ricerca import history, lavori
from ricerca.app import app
from ricerca.config import Config
from ricerca.llm import LLMClient, LLMError, _parse_sintesi
from ricerca.models import Block, SourceResult, Strategy, Work

client = TestClient(app)

RISPOSTA = {"choices": [{"message": {"content": '''{"metodo": "Studio su 116 studenti.",
 "risultati": "Il gruppo trattato ha posto più domande.",
 "discussione": "Gli autori dichiarano il limite del campione unico.",
 "conclusione": "Un laboratorio breve cambia il comportamento."}'''}}]}


def ricerca_con_abstract():
    works = [Work(title="Teaching students to question the machine", doi="10.1/x", year=2026,
                  abstract="Uno studio quasi sperimentale su 116 studenti di terza media…",
                  sources=["arxiv"])]
    return history.salva("t", Strategy([Block("C", ["x"])]),
                         [SourceResult("arxiv", "arXiv", "q", works=works)], works)


def con_modello():
    config_module.save(Config(llm_base_url="http://x/v1", llm_model="gemma4:12b-it-qat",
                              configurato="1"))


def test_le_quattro_parti_si_leggono_anche_da_una_risposta_sporca():
    parti = _parse_sintesi('```json\n{"metodo": "m", "risultati": "r", "discussione": "d", "conclusione": "c"}\n```')
    assert parti == {"metodo": "m", "risultati": "r", "discussione": "d", "conclusione": "c"}


def test_una_risposta_senza_riassunto_e_un_errore():
    with pytest.raises(LLMError):
        _parse_sintesi("non ho capito la richiesta")
    with pytest.raises(LLMError):
        _parse_sintesi('{"metodo": "", "risultati": "", "discussione": "", "conclusione": ""}')


@respx.mock
async def test_la_richiesta_chiede_le_quattro_parti_nella_lingua_scelta():
    rotta = respx.post("http://x/v1/chat/completions").mock(return_value=httpx.Response(200, json=RISPOSTA))
    config = Config(llm_base_url="http://x/v1", llm_model="m")

    await LLMClient(config).sintesi("Titolo", "Testo dell'articolo", "en")

    inviato = rotta.calls[0].request.content.decode()
    assert "in inglese" in inviato
    assert "metodo" in inviato and "conclusione" in inviato
    assert "nessuna informazione che non sia nel testo" in inviato


@respx.mock
async def test_il_testo_lungo_viene_troncato():
    rotta = respx.post("http://x/v1/chat/completions").mock(return_value=httpx.Response(200, json=RISPOSTA))
    await LLMClient(Config(llm_base_url="http://x/v1", llm_model="m")).sintesi("T", "x" * 50000, "it")
    assert len(rotta.calls[0].request.content) < 20000


@respx.mock
def test_il_riassunto_si_chiede_dalla_scheda_e_ci_resta():
    con_modello()
    respx.post("http://x/v1/chat/completions").mock(return_value=httpx.Response(200, json=RISPOSTA))
    id_ricerca = ricerca_con_abstract()

    avvio = client.post(f"/scheda/{id_ricerca}/0/sintesi", data={"lingua": "it"}).text
    assert "reading the article" in avvio          # torna subito, non aspetta

    for _ in range(200):
        if history.sintesi(id_ricerca, 0):
            break
        client.get(f"/scheda/{id_ricerca}/0")

    salvata = history.sintesi(id_ricerca, 0)
    assert salvata["metodo"].startswith("Studio su 116")
    assert salvata["lingua"] == "it" and salvata["modello"] == "gemma4:12b-it-qat"

    scheda = client.get(f"/scheda/{id_ricerca}/0").text
    assert "Method." in scheda and "Conclusion." in scheda
    assert "Studio su 116 studenti." in scheda
    assert "read it against the article" in scheda   # l'avvertenza resta


def test_senza_modello_la_scheda_lo_dice():
    config_module.save(Config(configurato="1"))
    id_ricerca = ricerca_con_abstract()
    scheda = client.get(f"/scheda/{id_ricerca}/0").text
    assert "A model is needed" in scheda
    assert "summarise in Italian" not in scheda


def test_senza_testo_non_si_propone_il_riassunto():
    con_modello()
    works = [Work(title="Senza abstract", doi="10.1/y")]
    id_ricerca = history.salva("t", Strategy([Block("C", ["x"])]),
                               [SourceResult("crossref", "Crossref", "q", works=works)], works)
    scheda = client.get(f"/scheda/{id_ricerca}/0").text
    assert "no text to summarise" in scheda


@respx.mock
def test_due_richieste_di_fila_non_avviano_due_lavori():
    con_modello()
    rotta = respx.post("http://x/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=RISPOSTA))
    id_ricerca = ricerca_con_abstract()

    client.post(f"/scheda/{id_ricerca}/0/sintesi", data={"lingua": "it"})
    client.post(f"/scheda/{id_ricerca}/0/sintesi", data={"lingua": "it"})

    for _ in range(200):
        if history.sintesi(id_ricerca, 0):
            break
        client.get(f"/scheda/{id_ricerca}/0")
    assert rotta.call_count == 1


@respx.mock
def test_l_attesa_interroga_e_non_riavvia_il_riassunto():
    """Il difetto era qui: l'attesa rifaceva la richiesta che avvia il lavoro,
    così appena il primo riassunto finiva ne partiva un altro, all'infinito."""

    con_modello()
    rotta = respx.post("http://x/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=RISPOSTA))
    id_ricerca = ricerca_con_abstract()

    avvio = client.post(f"/scheda/{id_ricerca}/0/sintesi", data={"lingua": "it"}).text
    assert 'hx-get="/scheda/' in avvio          # interroga
    assert "hx-post" not in avvio.split("scheda-riquadro sintesi")[1][:400]

    for _ in range(200):
        if history.sintesi(id_ricerca, 0):
            break
        client.get(f"/scheda/{id_ricerca}/0")

    # dieci giri dopo la fine: nessun altro riassunto avviato
    for _ in range(10):
        client.get(f"/scheda/{id_ricerca}/0")
    assert rotta.call_count == 1


@respx.mock
def test_chiedere_di_rifarlo_lo_rifa_una_volta_sola():
    con_modello()
    rotta = respx.post("http://x/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=RISPOSTA))
    id_ricerca = ricerca_con_abstract()

    client.post(f"/scheda/{id_ricerca}/0/sintesi", data={"lingua": "it"})
    for _ in range(200):
        if history.sintesi(id_ricerca, 0):
            break
        client.get(f"/scheda/{id_ricerca}/0")

    # senza chiederlo non si rifà
    client.post(f"/scheda/{id_ricerca}/0/sintesi", data={"lingua": "en"})
    assert rotta.call_count == 1

    # chiedendolo, sì
    client.post(f"/scheda/{id_ricerca}/0/sintesi", data={"lingua": "en", "rifai": "1"})
    for _ in range(200):
        client.get(f"/scheda/{id_ricerca}/0")
        if rotta.call_count > 1:
            break
    assert rotta.call_count == 2


@respx.mock
def test_a_riassunto_fatto_la_scheda_offre_di_rifarlo():
    con_modello()
    respx.post("http://x/v1/chat/completions").mock(return_value=httpx.Response(200, json=RISPOSTA))
    id_ricerca = ricerca_con_abstract()
    client.post(f"/scheda/{id_ricerca}/0/sintesi", data={"lingua": "it"})
    for _ in range(200):
        if history.sintesi(id_ricerca, 0):
            break
        client.get(f"/scheda/{id_ricerca}/0")

    scheda = client.get(f"/scheda/{id_ricerca}/0").text
    assert "summarise again" in scheda
    assert '"rifai": "1"' in scheda
