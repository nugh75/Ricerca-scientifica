"""Apertura in una finestra propria, senza barre del browser.

I browser della famiglia Chromium hanno `--app=<indirizzo>`: aprono una
finestra pulita, senza barra degli indirizzi né schede. Non si può sapere in
anticipo quale browser avrà chi installa l'app, quindi si cercano tutti quelli
noti e, se non c'è nessuno, si ripiega sul browser predefinito.

Per Safari, che `--app` non ce l'ha, la strada è il manifesto web: dal menu
Condividi → «Aggiungi al Dock» l'app ottiene comunque la sua finestra.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import webbrowser
from pathlib import Path

# Nomi da cercare nel PATH, in ordine di diffusione.
COMANDI = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "brave-browser",
    "microsoft-edge",
    "vivaldi",
)

# Percorsi fissi: su macOS e Windows i browser non stanno nel PATH.
PERCORSI = {
    "Darwin": (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
    ),
    "Windows": (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    ),
}


def trova_browser(sistema: str | None = None) -> str | None:
    """Il primo browser capace di aprire una finestra senza barre."""

    for comando in COMANDI:
        trovato = shutil.which(comando)
        if trovato:
            return trovato
    for percorso in PERCORSI.get(sistema or platform.system(), ()):
        if Path(percorso).exists():
            return percorso
    return None


def apri(url: str, finestra_propria: bool = True) -> str:
    """Apre l'app. Ritorna come è stata aperta, per dirlo a chi guarda."""

    if finestra_propria:
        browser = trova_browser()
        if browser:
            try:
                subprocess.Popen(
                    [browser, f"--app={url}", "--window-size=1280,900"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return "finestra"
            except OSError:
                pass  # browser presente ma non avviabile: si ripiega
    webbrowser.open(url)
    return "browser"
