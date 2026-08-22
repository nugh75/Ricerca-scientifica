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


# Nome leggibile a partire dall'eseguibile: nell'elenco delle Impostazioni
# «google-chrome-stable» non dice niente a chi legge.
ETICHETTE = {
    "google-chrome": "Google Chrome",
    "google-chrome-stable": "Google Chrome",
    "chrome": "Google Chrome",
    "chromium": "Chromium",
    "chromium-browser": "Chromium",
    "brave-browser": "Brave",
    "brave": "Brave",
    "microsoft-edge": "Microsoft Edge",
    "msedge": "Microsoft Edge",
    "vivaldi": "Vivaldi",
}

# Il browser di sistema: apre una scheda normale e non sa fare `--app`.
PREDEFINITO = "predefinito"


def etichetta(percorso: str) -> str:
    """«/usr/bin/google-chrome-stable» → «Google Chrome»."""

    nome = Path(percorso).stem
    return ETICHETTE.get(nome.lower(), nome.replace("-", " ").title())


def browser_disponibili(sistema: str | None = None) -> list[dict]:
    """I browser capaci di una finestra senza barre, trovati su questa macchina.

    Servono a far scegliere: chi ha Chrome per lavoro e Brave per il resto
    non vuole che l'app decida al posto suo.
    """

    trovati: list[dict] = []
    visti: set[str] = set()
    # Quel che torna da `which` esiste già; i percorsi fissi vanno verificati.
    candidati = [shutil.which(comando) for comando in COMANDI]
    candidati += [
        percorso for percorso in PERCORSI.get(sistema or platform.system(), ())
        if Path(percorso).exists()
    ]
    for percorso in candidati:
        if not percorso or percorso in visti:
            continue
        visti.add(percorso)
        nome = etichetta(percorso)
        if any(voce["etichetta"] == nome for voce in trovati):
            continue        # stesso browser trovato due volte, in due posti
        trovati.append({"percorso": percorso, "etichetta": nome})
    return trovati


def trova_browser(sistema: str | None = None) -> str | None:
    """Il primo browser capace di aprire una finestra senza barre."""

    disponibili = browser_disponibili(sistema)
    return disponibili[0]["percorso"] if disponibili else None


def eseguibile(browser: str = "") -> str | None:
    """Il programma da lanciare: quello scelto, se c'è ancora, o il primo.

    Una scelta che non vale più — il browser è stato disinstallato, o la
    configurazione arriva da un'altra macchina — non deve impedire l'avvio:
    si torna a cercare, come se non fosse stato scelto niente.
    """

    if browser == PREDEFINITO:
        return None
    if browser:
        percorso = shutil.which(browser)
        if percorso:
            return percorso
        if Path(browser).exists():
            return browser
    return trova_browser()


def apri(url: str, finestra_propria: bool = True, browser: str = "") -> str:
    """Apre l'app. Ritorna come è stata aperta, per dirlo a chi guarda."""

    # Senza una scelta esplicita, la scheda resta affare del browser di
    # sistema: è quello che l'utente si aspetta di vedere aprirsi, e non c'è
    # motivo di andare a cercarne altri.
    scelto = (
        eseguibile(browser)
        if finestra_propria or browser not in ("", PREDEFINITO)
        else None
    )
    if scelto:
        argomenti = (
            [scelto, f"--app={url}", "--window-size=1280,900"]
            if finestra_propria
            else [scelto, url]
        )
        try:
            subprocess.Popen(
                argomenti, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return "finestra" if finestra_propria else "scheda"
        except OSError:
            pass  # browser presente ma non avviabile: si ripiega
    webbrowser.open(url)
    return "browser"
