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
