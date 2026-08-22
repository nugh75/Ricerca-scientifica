import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from ricerca import finestra
from ricerca.app import app
from ricerca.cli import main

client = TestClient(app)


def test_cerca_i_browser_noti_nel_path(monkeypatch):
    monkeypatch.setattr(finestra.shutil, "which", lambda nome: "/usr/bin/x" if nome == "chromium" else None)
    assert finestra.trova_browser() == "/usr/bin/x"


def test_su_mac_guarda_dentro_applications(monkeypatch, tmp_path):
    monkeypatch.setattr(finestra.shutil, "which", lambda _: None)
    finto = tmp_path / "Chrome"
    finto.write_text("")
    monkeypatch.setattr(finestra, "PERCORSI", {"Darwin": (str(finto),)})
    assert finestra.trova_browser("Darwin") == str(finto)
    assert finestra.trova_browser("Linux") is None


def test_senza_browser_chromium_si_ripiega_sul_predefinito(monkeypatch):
    monkeypatch.setattr(finestra, "trova_browser", lambda *_: None)
    aperti = []
    monkeypatch.setattr(finestra.webbrowser, "open", aperti.append)
    assert finestra.apri("http://127.0.0.1:8000") == "browser"
    assert aperti == ["http://127.0.0.1:8000"]


def test_con_chromium_apre_una_finestra_senza_barre(monkeypatch):
    monkeypatch.setattr(finestra, "trova_browser", lambda *_: "/usr/bin/chromium")
    comandi = []
    monkeypatch.setattr(finestra.subprocess, "Popen", lambda cmd, **kw: comandi.append(cmd))
    assert finestra.apri("http://127.0.0.1:8000") == "finestra"
    assert comandi[0][:2] == ["/usr/bin/chromium", "--app=http://127.0.0.1:8000"]


def test_un_browser_che_non_parte_non_blocca_l_avvio(monkeypatch):
    monkeypatch.setattr(finestra, "trova_browser", lambda *_: "/usr/bin/chromium")

    def esplode(*_args, **_kw):
        raise OSError("non eseguibile")

    monkeypatch.setattr(finestra.subprocess, "Popen", esplode)
    aperti = []
    monkeypatch.setattr(finestra.webbrowser, "open", aperti.append)
    assert finestra.apri("http://x") == "browser"
    assert aperti == ["http://x"]


def test_l_opzione_scheda_evita_la_finestra_propria(monkeypatch):
    chiamate = []
    monkeypatch.setattr(finestra, "trova_browser", lambda *_: chiamate.append("cercato"))
    monkeypatch.setattr(finestra.webbrowser, "open", lambda _u: None)
    assert finestra.apri("http://x", finestra_propria=False) == "browser"
    assert chiamate == []


def test_il_manifesto_e_servito_e_valido():
    risposta = client.get("/static/manifest.webmanifest")
    assert risposta.status_code == 200
    dati = json.loads(risposta.text)
    assert dati["display"] == "standalone"
    assert dati["start_url"] == "/"
    assert any(icona["sizes"] == "512x512" for icona in dati["icons"])


def test_la_pagina_dichiara_il_manifesto_e_le_icone():
    pagina = client.get("/").text
    assert '<link rel="manifest" href="/static/manifest.webmanifest">' in pagina
    assert 'rel="apple-touch-icon"' in pagina
    assert 'name="theme-color"' in pagina


def test_le_icone_del_manifesto_esistono():
    statici = Path(__file__).resolve().parent.parent / "ricerca/static"
    for nome in ("icona.png", "icona-192.png", "icona-180.png"):
        assert (statici / nome).exists(), nome


def test_l_aiuto_spiega_l_opzione_scheda(capsys):
    main([])
    assert "serve" in capsys.readouterr().out


def test_l_avvio_apre_la_finestra_propria(monkeypatch, tmp_path):
    """Dal comando `serve` alla finestra: la catena completa, senza rete."""

    import ricerca.cli as cli

    browser_finto = tmp_path / "chrome-finto"
    browser_finto.write_text("#!/bin/sh\necho \"$@\" > \"$(dirname \"$0\")/argomenti\"\n")
    browser_finto.chmod(0o755)
    monkeypatch.setattr(finestra, "trova_browser", lambda *_: str(browser_finto))

    avviato = {}
    monkeypatch.setattr(cli.uvicorn, "run", lambda *a, **k: avviato.update(k))

    class TimerImmediato:
        def __init__(self, _ritardo, funzione, args=()):
            self.funzione, self.args = funzione, args

        def start(self):
            self.funzione(*self.args)

    monkeypatch.setattr(cli.threading, "Timer", TimerImmediato)
    monkeypatch.setattr(cli, "free_port", lambda *_a, **_k: 8123)

    assert cli.main(["serve"]) == 0

    subprocess.run(["sh", "-c", "sleep 0.3"], check=True)
    assert "--app=http://127.0.0.1:8123" in (tmp_path / "argomenti").read_text()
    assert avviato["host"] == "127.0.0.1"


def test_con_no_browser_non_si_apre_niente(monkeypatch):
    import ricerca.cli as cli

    monkeypatch.setattr(cli.uvicorn, "run", lambda *a, **k: None)
    monkeypatch.setattr(cli, "free_port", lambda *_a, **_k: 8124)
    aperture = []
    monkeypatch.setattr(finestra, "apri", lambda *a, **k: aperture.append(a))
    assert cli.main(["serve", "--no-browser"]) == 0
    assert aperture == []


def test_ogni_classe_dei_template_ha_una_regola_di_stile():
    """Una classe senza regola passa i test ma sfalda la pagina."""

    import re
    from pathlib import Path

    radice = Path(__file__).resolve().parent.parent
    modelli = list((radice / "ricerca/templates").rglob("*.html"))
    usate = set()
    for modello in modelli:
        for gruppo in re.findall(r'class="([a-z0-9 _-]+)"', modello.read_text()):
            usate.update(gruppo.split())

    foglio = (radice / "ricerca/static/style.css").read_text()
    definite = set(re.findall(r"\.([a-z][a-z0-9_-]*)", foglio))
    # Alcune classi sono solo agganci per htmx o per il codice, non per lo stile.
    solo_agganci = {"salta"}   # form senza campi, agganciato dai bottoni

    assert not (usate - definite - solo_agganci)


def test_elenca_i_browser_trovati_con_un_nome_leggibile(monkeypatch, tmp_path):
    finto = tmp_path / "Google Chrome"
    finto.write_text("")
    monkeypatch.setattr(
        finestra.shutil, "which",
        lambda nome: "/usr/bin/brave-browser" if nome == "brave-browser" else None,
    )
    monkeypatch.setattr(finestra, "PERCORSI", {"Darwin": (str(finto),)})

    trovati = finestra.browser_disponibili("Darwin")

    assert [voce["etichetta"] for voce in trovati] == ["Brave", "Google Chrome"]
    assert trovati[0]["percorso"] == "/usr/bin/brave-browser"


def test_lo_stesso_browser_trovato_due_volte_compare_una_volta_sola(monkeypatch):
    monkeypatch.setattr(
        finestra.shutil, "which",
        lambda nome: f"/usr/bin/{nome}" if nome in ("google-chrome", "google-chrome-stable") else None,
    )
    monkeypatch.setattr(finestra, "PERCORSI", {})
    assert [v["etichetta"] for v in finestra.browser_disponibili("Linux")] == ["Google Chrome"]


def test_il_browser_scelto_e_quello_che_parte(monkeypatch):
    monkeypatch.setattr(finestra.shutil, "which", lambda nome: f"/usr/bin/{nome}")
    comandi = []
    monkeypatch.setattr(finestra.subprocess, "Popen", lambda cmd, **kw: comandi.append(cmd))

    assert finestra.apri("http://x", browser="vivaldi") == "finestra"
    assert comandi[0][:2] == ["/usr/bin/vivaldi", "--app=http://x"]


def test_il_browser_scelto_apre_anche_una_scheda_normale(monkeypatch):
    monkeypatch.setattr(finestra.shutil, "which", lambda nome: f"/usr/bin/{nome}")
    comandi = []
    monkeypatch.setattr(finestra.subprocess, "Popen", lambda cmd, **kw: comandi.append(cmd))

    assert finestra.apri("http://x", finestra_propria=False, browser="vivaldi") == "scheda"
    assert comandi[0] == ["/usr/bin/vivaldi", "http://x"]      # nessun --app


def test_chiedendo_il_predefinito_non_si_cerca_nessuna_finestra(monkeypatch):
    cercati = []
    monkeypatch.setattr(finestra, "trova_browser", lambda *_: cercati.append("cercato"))
    aperti = []
    monkeypatch.setattr(finestra.webbrowser, "open", aperti.append)

    assert finestra.apri("http://x", browser=finestra.PREDEFINITO) == "browser"
    assert aperti == ["http://x"]
    assert cercati == []


def test_una_scelta_che_non_esiste_piu_non_impedisce_l_avvio(monkeypatch):
    monkeypatch.setattr(finestra.shutil, "which", lambda _: None)
    monkeypatch.setattr(finestra, "trova_browser", lambda *_: "/usr/bin/chromium")
    comandi = []
    monkeypatch.setattr(finestra.subprocess, "Popen", lambda cmd, **kw: comandi.append(cmd))

    assert finestra.apri("http://x", browser="/opt/browser-sparito") == "finestra"
    assert comandi[0][0] == "/usr/bin/chromium"
