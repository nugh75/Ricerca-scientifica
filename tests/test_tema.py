from fastapi.testclient import TestClient

from ricerca import config as config_module
from ricerca.app import app
from ricerca.config import Config

client = TestClient(app)


def test_di_partenza_segue_il_sistema():
    assert 'data-tema="auto"' in client.get("/").text


def test_la_scelta_del_tema_resta():
    client.post("/tema/scuro")
    assert config_module.load().tema == "scuro"
    assert 'data-tema="scuro"' in client.get("/").text

    client.post("/tema/chiaro")
    assert 'data-tema="chiaro"' in client.get("/").text


def test_un_tema_inventato_ricade_su_auto():
    client.post("/tema/fucsia")
    assert config_module.load().tema == "auto"


def test_il_bottone_scelto_e_evidenziato():
    pagina = client.post("/tema/scuro").text
    assert 'class="scelta-preferenza attiva"' in pagina
    assert 'aria-pressed="true"' in pagina
    assert ">dark</button>" in pagina


def test_le_impostazioni_non_azzerano_il_tema():
    client.post("/tema/scuro")
    client.post("/impostazioni", data={
        "mailto": "x@y.it", "llm_base_url": "", "llm_model": "", "llm_api_key": "",
        "core_api_key": "", "s2_api_key": "", "ncbi_api_key": "",
        "zotero_api_key": "", "zotero_library_id": "", "zotero_library_type": "users",
    })
    assert config_module.load().tema == "scuro"


def test_il_cambio_lingua_non_azzera_il_tema():
    client.post("/tema/chiaro")
    client.post("/lingua/it")
    assert config_module.load().tema == "chiaro"
    assert config_module.load().lang == "it"


def test_nessun_collegamento_resta_al_blu_del_browser():
    """Il blu predefinito è illeggibile sul tema scuro: serve una regola."""

    import re
    from pathlib import Path

    foglio = (Path(__file__).resolve().parent.parent / "ricerca/static/style.css").read_text()
    regola = re.search(r"\na \{(.*?)\}", foglio, re.S)
    assert regola, "manca la regola generale per i collegamenti"
    assert "var(--accento)" in regola.group(1)
    # e i collegamenti travestiti da tasto seguono i tasti
    assert "button, a.tasto, a.copia {" in foglio


def test_l_accento_del_tema_scuro_e_chiaro_abbastanza():
    """Su fondo #17191c serve un accento chiaro, non il blu di sistema."""

    from pathlib import Path

    foglio = (Path(__file__).resolve().parent.parent / "ricerca/static/style.css").read_text()
    scuro = foglio[foglio.index('html[data-tema="scuro"]'):]
    accento = scuro[scuro.index("--accento:"):].split(";")[0]
    canali = [int(accento.strip()[-6:][i:i + 2], 16) for i in (0, 2, 4)]
    luminosita = (0.299 * canali[0] + 0.587 * canali[1] + 0.114 * canali[2]) / 255
    assert luminosita > 0.55, f"accento troppo scuro sul fondo scuro: {accento}"


def test_le_impostazioni_fanno_scegliere_come_si_apre_e_con_quale_browser(monkeypatch):
    from ricerca import config as config_module, finestra
    from ricerca.app import app as applicazione
    from fastapi.testclient import TestClient as Client

    cliente = Client(applicazione)
    monkeypatch.setattr(
        finestra, "browser_disponibili",
        lambda *_: [{"percorso": "/usr/bin/vivaldi", "etichetta": "Vivaldi"}],
    )

    pagina = cliente.get("/impostazioni").text
    assert "How it opens" in pagina
    assert "Vivaldi" in pagina
    assert 'value="predefinito"' in pagina

    cliente.post("/impostazioni", data={
        "mailto": "", "llm_base_url": "", "llm_model": "", "llm_api_key": "",
        "core_api_key": "", "s2_api_key": "", "ncbi_api_key": "",
        "apertura": "scheda", "browser": "/usr/bin/vivaldi",
    })

    salvata = config_module.load()
    assert salvata.apertura == "scheda"
    assert salvata.browser == "/usr/bin/vivaldi"


def test_un_browser_scelto_e_sparito_resta_visibile_nell_elenco(monkeypatch):
    from ricerca import config as config_module, finestra
    from ricerca.app import app as applicazione
    from ricerca.config import Config
    from fastapi.testclient import TestClient as Client

    config_module.save(Config(configurato="1", browser="/opt/browser-sparito"))
    monkeypatch.setattr(finestra, "browser_disponibili", lambda *_: [])
    pagina = Client(applicazione).get("/impostazioni").text

    assert "/opt/browser-sparito" in pagina
    assert "no longer found" in pagina
    assert "No Chromium-family browser found" in pagina
