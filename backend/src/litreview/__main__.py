import os
import socket
import sys
import threading
import webbrowser

import uvicorn

from . import config

HOST = "127.0.0.1"
PORT = 8756
DOCS_URL = f"http://{HOST}:{PORT}/docs"

BROWSER_DELAY = 1.5


def _open_browser() -> None:
    webbrowser.open(DOCS_URL)


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((host, port)) == 0


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
    if _port_in_use(HOST, PORT):
        _warn(
            f"Impossibile avviare il server: la porta {PORT} e' gia' occupata "
            "da un altro processo. Chiudilo e riprova."
        )
        return 1
    _redirect_logs_if_frozen()
    if os.environ.get("LITREVIEW_NO_BROWSER") != "1":
        threading.Timer(BROWSER_DELAY, _open_browser).start()
    uvicorn.run("litreview.main:app", host=HOST, port=PORT, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
