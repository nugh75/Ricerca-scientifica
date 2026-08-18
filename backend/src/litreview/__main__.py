import json
import os
import socket
import sys
import threading
import urllib.error
import urllib.request
import webbrowser

import uvicorn

from . import config

HOST = "127.0.0.1"
DEFAULT_PORT = 8756
PORT_SCAN_LIMIT = 10
PROBE_TIMEOUT = 0.3

BROWSER_DELAY = 1.5


def docs_url(port: int) -> str:
    return f"http://{HOST}:{port}/docs"


def _open_browser(port: int) -> None:
    webbrowser.open(docs_url(port))


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((host, port)) == 0


def _is_litreview(host: str, port: int) -> bool:
    """Tell our own backend from any other process holding the port."""
    try:
        with urllib.request.urlopen(
            f"http://{host}:{port}/health", timeout=PROBE_TIMEOUT
        ) as res:
            return json.load(res).get("app") == "litreview"
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _resolve_port(host: str) -> tuple[int, bool] | None:
    """Return (port, reused) for the first usable port, or None if there is none.

    A port already served by LitReview is reused instead of starting a second
    server on the same library: both instances would write the same SQLite file.
    """
    for port in range(DEFAULT_PORT, DEFAULT_PORT + PORT_SCAN_LIMIT):
        if not _port_in_use(host, port):
            return port, False
        if _is_litreview(host, port):
            return port, True
    return None


def _announce(port: int, reused: bool) -> None:
    """Publish the chosen port on stdout for the desktop app to read.

    Must run before _redirect_logs_if_frozen(): afterwards stdout is server.log
    and the desktop app would never learn which port to talk to.
    """
    if sys.stdout is None:
        return
    print(f"LITREVIEW_REUSED={1 if reused else 0}", flush=True)
    print(f"LITREVIEW_PORT={port}", flush=True)


def _redirect_logs_if_frozen() -> None:
    if not getattr(sys, "frozen", False):
        return
    if sys.stdout is not None and sys.stdout.isatty():
        return
    config.APP_DIR.mkdir(parents=True, exist_ok=True)
    log_file = open(config.APP_DIR / "server.log", "a", encoding="utf-8")
    sys.stdout = log_file
    sys.stderr = log_file


def _warn(msg: str) -> None:
    if sys.stderr is not None:
        print(msg, file=sys.stderr)
    if getattr(sys, "frozen", False):
        config.APP_DIR.mkdir(parents=True, exist_ok=True)
        with open(config.APP_DIR / "server.log", "a", encoding="utf-8") as log_file:
            print(msg, file=log_file)


def main() -> int:
    resolved = _resolve_port(HOST)
    if resolved is None:
        last = DEFAULT_PORT + PORT_SCAN_LIMIT - 1
        _warn(
            f"Impossibile avviare il server: le porte da {DEFAULT_PORT} a {last} sono "
            "tutte occupate da altri processi. Chiudine qualcuno e riprova."
        )
        return 1
    port, reused = resolved
    _announce(port, reused)
    open_browser = os.environ.get("LITREVIEW_NO_BROWSER") != "1"

    if reused:
        _warn(
            f"LitReview e' gia' in esecuzione su {docs_url(port)}. "
            "Apro l'istanza esistente invece di avviarne una seconda."
        )
        if open_browser:
            _open_browser(port)
        return 0

    _redirect_logs_if_frozen()
    if open_browser:
        threading.Timer(BROWSER_DELAY, _open_browser, (port,)).start()
    uvicorn.run("litreview.main:app", host=HOST, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
