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
    for nome in ("avvia.sh", "packaging/macos/avvio"):
        testo = (RADICE / nome).read_text()
        assert 'INSTALLATA=' in testo, nome
        assert '!= "$VERSIONE"' in testo, nome
        assert re.search(r'echo "\$VERSIONE" >', testo), nome


def test_il_bundle_dichiara_la_stessa_versione():
    plist = (RADICE / "packaging/macos/Info.plist").read_text()
    assert f"<string>{versione_dichiarata()}</string>" in plist


def test_i_lanciatori_ricreano_l_ambiente_senza_inciampare():
    """`uv venv` fallisce su un ambiente esistente: serve --clear."""

    for nome in ("avvia.sh", "packaging/macos/avvio"):
        testo = (RADICE / nome).read_text()
        assert "venv --quiet --clear" in testo or "venv --clear" in testo, nome
    assert "venv --quiet --clear" in (RADICE / "avvia.bat").read_text()


def test_anche_windows_confronta_la_versione():
    testo = (RADICE / "avvia.bat").read_text()
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
    testo = (RADICE / "packaging/macos/avvio").read_text()
    assert 'echo "bundle: $BUNDLE"' in testo


def test_esiste_un_solo_lanciatore_per_unix():
    """Una copia del lanciatore resterebbe indietro senza che nessuno se ne
    accorga: è già successo con avvia.command, rimasto senza il confronto di
    versione per otto rilasci."""

    assert (RADICE / "avvia.sh").exists()
    assert not (RADICE / "avvia.command").exists()
    costruzione = (RADICE / "scripts/crea-release.sh").read_text()
    assert 'cp avvia.sh "$MAC/avvia-da-terminale.command"' in costruzione


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
