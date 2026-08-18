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
