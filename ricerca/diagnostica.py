"""Da dove viene il codice che sta girando.

Su macOS può restare in giro una copia vecchia di Ricerca.app: senza questi
dati non c'è modo di accorgersene, si vede solo un'app che «non cambia».
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from . import __version__
from . import config as config_module


def dati() -> dict:
    pacchetto = Path(__file__).resolve().parent
    venv = config_module.CONFIG_DIR / "venv"
    marcatore = venv / ".versione"
    return {
        "versione": __version__,
        "pacchetto": str(pacchetto),
        "app": str(_cartella_app(pacchetto)),
        "python": sys.executable,
        "venv_versione": marcatore.read_text(encoding="utf-8").strip()
        if marcatore.exists()
        else "",
        "configurazione": str(config_module.CONFIG_FILE),
        "sistema": f"{platform.system()} {platform.release()}",
        "allineata": _allineata(marcatore),
    }


def _cartella_app(pacchetto: Path) -> Path:
    """Il bundle macOS, se il codice arriva da lì; altrimenti la cartella."""

    for genitore in pacchetto.parents:
        if genitore.suffix == ".app":
            return genitore
    return pacchetto.parent


def _allineata(marcatore: Path) -> bool:
    if not marcatore.exists():
        return True  # avviata dal sorgente: non c'è nulla da confrontare
    return marcatore.read_text(encoding="utf-8").strip() == __version__
