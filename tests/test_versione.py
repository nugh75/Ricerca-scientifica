import re
import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

from ricerca import __version__
from ricerca.app import app

client = TestClient(app)
RADICE = Path(__file__).resolve().parent.parent


def versione_dichiarata() -> str:
    with (RADICE / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def test_la_versione_del_pacchetto_e_quella_dichiarata():
    assert __version__ == versione_dichiarata()


def test_la_pagina_mostra_la_versione():
    pagina = client.get("/").text
    assert f"Ricerca {__version__}" in pagina


def test_i_file_statici_portano_la_versione():
    pagina = client.get("/").text
    assert f"/static/style.css?v={__version__}" in pagina
    assert f"/static/htmx.min.js?v={__version__}" in pagina


def test_i_lanciatori_reinstallano_quando_la_versione_cambia():
    for nome in ("start.sh", "packaging/macos/launch"):
        testo = (RADICE / nome).read_text()
        assert 'INSTALLATA=' in testo, nome
        assert '!= "$VERSIONE"' in testo, nome
        assert re.search(r'echo "\$VERSIONE" >', testo), nome


def test_il_bundle_prende_la_versione_dalla_costruzione():
    """Il plist portava il numero scritto a mano e la sostituzione cercava una
    versione ferma a 1.3.0: il bundle rischiava di dichiararsi vecchio a ogni
    rilascio. Ora il segnaposto viene riempito da chi costruisce."""

    plist = (RADICE / "packaging/macos/Info.plist").read_text()
    for chiave in ("CFBundleVersion", "CFBundleShortVersionString"):
        assert f"<key>{chiave}</key><string>__VERSIONE__</string>" in plist, chiave
    costruzione = (RADICE / "scripts/crea-release.sh").read_text()
    assert 's/__VERSIONE__/$VERSIONE/g' in costruzione
    riempito = plist.replace("__VERSIONE__", versione_dichiarata())
    assert f"<string>{versione_dichiarata()}</string>" in riempito


def test_i_lanciatori_ricreano_l_ambiente_senza_inciampare():
    """`uv venv` fallisce su un ambiente esistente: serve --clear."""

    for nome in ("start.sh", "packaging/macos/launch"):
        testo = (RADICE / nome).read_text()
        assert "venv --quiet --clear" in testo or "venv --clear" in testo, nome
    assert "venv --quiet --clear" in (RADICE / "start.bat").read_text()


def test_anche_windows_confronta_la_versione():
    testo = (RADICE / "start.bat").read_text()
    assert "INSTALLATA" in testo
    assert '.versione' in testo


def test_la_diagnosi_dice_da_dove_arriva_il_codice():
    from ricerca import diagnostica

    dati = diagnostica.dati()
    assert dati["versione"] == __version__
    assert dati["pacchetto"].endswith("ricerca")
    assert dati["configurazione"].endswith("config.toml")


def test_la_diagnosi_riconosce_un_ambiente_disallineato(isolated_config):
    from ricerca import diagnostica

    venv = isolated_config / "venv"
    venv.mkdir()
    (venv / ".versione").write_text("0.0.1")
    assert diagnostica.dati()["allineata"] is False
    assert diagnostica.dati()["venv_versione"] == "0.0.1"


def test_la_pagina_impostazioni_mostra_la_diagnosi():
    pagina = client.get("/impostazioni").text
    assert "Which copy is running" in pagina
    assert __version__ in pagina


def test_il_comando_versione_stampa_i_percorsi(capsys):
    from ricerca.cli import main

    assert main(["versione"]) == 0
    stampato = capsys.readouterr().out
    assert __version__ in stampato
    assert "configurazione" in stampato


def test_il_bundle_registra_quale_copia_parte():
    testo = (RADICE / "packaging/macos/launch").read_text()
    assert 'echo "bundle: $BUNDLE"' in testo


def test_esiste_un_solo_lanciatore_per_unix():
    """Una copia del lanciatore resterebbe indietro senza che nessuno se ne
    accorga: è già successo con avvia.command, rimasto senza il confronto di
    versione per otto rilasci."""

    assert (RADICE / "start.sh").exists()
    assert not (RADICE / "start.command").exists()
    costruzione = (RADICE / "scripts/crea-release.sh").read_text()
    assert 'cp start.sh "$MAC/start-from-terminal.command"' in costruzione


def test_il_repository_non_porta_file_altrui():
    """Mappa dei progetti dell'utente e collegamenti alle skill locali non
    appartengono a un'app che altri scaricano."""

    import subprocess

    tracciati = subprocess.run(
        ["git", "ls-files"], cwd=RADICE, capture_output=True, text=True, check=True
    ).stdout.split()

    assert "PROJECTS.md" not in tracciati
    assert not [f for f in tracciati if f.startswith((".claude/", ".agents/", ".ai4educ/"))]


def test_nessun_collegamento_simbolico_esce_dal_repository():
    import subprocess

    righe = subprocess.run(
        ["git", "ls-files", "-s"], cwd=RADICE, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    simbolici = [r.split("\t")[1] for r in righe if r.startswith("120000")]
    assert simbolici == []


def test_la_costruzione_rifa_gli_archivi_invece_di_aggiungerci():
    """`zip` aggiunge a un archivio esistente: senza pulizia lo zip di oggi
    conteneva ancora i file di ieri."""

    costruzione = (RADICE / "scripts/crea-release.sh").read_text()
    assert 'rm -f "$DIST/ricerca-$VERSIONE"-*.tar.gz "$DIST/ricerca-$VERSIONE"-*.zip' in costruzione
    assert "cp -r docs/screenshot" not in costruzione   # le schermate non si distribuiscono


def test_i_nomi_dei_file_che_l_utente_vede_sono_in_inglese():
    """L'interfaccia parte in inglese: i file scaricati devono seguirla."""

    import re

    app = (RADICE / "ricerca/app.py").read_text()
    scaricati = set(re.findall(r'filename="([^"{]+)"', app))
    assert scaricati == {
        "references.bib", "records.csv", "apa-references.txt",
        "search-protocol.md", "search-protocol.txt",
        "article-pdfs.zip", "activity.log",
        "review-workspace.md", "review-workspace.json",
    }


def test_i_lanciatori_hanno_nomi_inglesi():
    for nome in ("start.sh", "start.bat"):
        assert (RADICE / nome).exists(), nome
    for vecchio in ("avvia.sh", "avvia.bat", "avvia.command"):
        assert not (RADICE / vecchio).exists(), vecchio
    assert (RADICE / "packaging/install-shortcut-linux.sh").exists()
    assert (RADICE / "packaging/create-shortcut-windows.bat").exists()


def test_ogni_archivio_porta_un_installatore_che_sostituisce_la_copia_precedente():
    installatori = {
        "packaging/install-linux.sh": ".local/share/ricerca",
        "packaging/install-macos.command": "Applications/Ricerca.app",
        "packaging/install-windows.ps1": "LOCALAPPDATA",
    }
    for nome, destinazione in installatori.items():
        testo = (RADICE / nome).read_text()
        assert destinazione in testo, nome
        assert "previous" in testo.lower(), nome

    costruzione = (RADICE / "scripts/crea-release.sh").read_text()
    assert 'install-or-update.sh' in costruzione
    assert 'install-or-update.command' in costruzione
    assert 'Ricerca.app install-or-update.command' in costruzione
    assert 'install-or-update.bat' in costruzione
    assert 'install-or-update.ps1' in costruzione


def test_le_copie_installate_tengono_l_ambiente_fuori_dalla_cartella_sostituibile():
    assert '.installed' in (RADICE / "packaging/install-linux.sh").read_text()
    assert '.installed' in (RADICE / "packaging/install-windows.ps1").read_text()
    assert '.installed' in (RADICE / "start.sh").read_text()
    assert '.installed' in (RADICE / "start.bat").read_text()


def test_l_archivio_non_contiene_nomi_italiani():
    """Solo i nomi dei file copiati: i commenti dello script restano in
    italiano come tutto il codice."""

    import re

    costruzione = (RADICE / "scripts/crea-release.sh").read_text()
    copiati = re.findall(r'(?:cp|cat >) [^\n]*?"\$(?:LINUX|MAC|WIN|BASE)/([A-Za-z0-9._-]+)"', costruzione)
    for nome in copiati:
        assert not any(p in nome.lower() for p in ("avvia", "leggimi", "scorciatoia")), nome
    assert "READ-ME-FIRST.txt" in costruzione
    assert "start-from-terminal.command" in costruzione


def test_i_file_nella_cartella_dati_hanno_nomi_inglesi(isolated_config):
    from ricerca import history, registro

    registro.annota("prova")
    history.salva("t", __import__("ricerca.models", fromlist=["m"]).Strategy(), [], [])

    nomi = {p.name for p in isolated_config.iterdir()}
    assert "activity.log" in nomi and "attivita.log" not in nomi
    assert "history.json" in nomi and "cronologia.json" not in nomi


def test_i_file_vecchi_vengono_traslocati_non_persi(isolated_config):
    """Chi aggiorna non deve perdere cronologia e registro."""

    from ricerca import history, registro

    (isolated_config / "cronologia.json").write_text('[{"id": "vecchia", "topic": "prima"}]')
    (isolated_config / "attivita.log").write_text("riga di ieri\n")

    assert history.elenco()[0]["topic"] == "prima"
    registro.annota("oggi")

    assert (isolated_config / "history.json").exists()
    assert not (isolated_config / "cronologia.json").exists()
    assert "riga di ieri" in (isolated_config / "activity.log").read_text()


def test_il_programma_e_libero_e_lo_dice():
    """La GPL vuole che il testo viaggi con il programma: chi scarica
    l'archivio deve trovarlo dentro, non solo sul sito."""

    licenza = (RADICE / "LICENSE").read_text()
    assert "GNU GENERAL PUBLIC LICENSE" in licenza
    assert "Version 3" in licenza

    with (RADICE / "pyproject.toml").open("rb") as fh:
        assert tomllib.load(fh)["project"]["license"] == "GPL-3.0-or-later"

    costruzione = (RADICE / "scripts/crea-release.sh").read_text()
    assert "README.md LICENSE" in costruzione
