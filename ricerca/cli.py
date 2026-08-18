"""Avvio dell'app: porta libera, bind su 127.0.0.1, browser aperto da solo."""

from __future__ import annotations

import argparse
import os
import socket
import threading
import webbrowser

import uvicorn

from . import watchdog


def free_port(start: int = 8000, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit(f"nessuna porta libera fra {start} e {start + attempts - 1}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ricerca", description="Assistente di strategia di ricerca bibliografica")
    sub = parser.add_subparsers(dest="comando")
    serve = sub.add_parser("serve", help="avvia l'app e apre il browser")
    serve.add_argument("--port", type=int, default=8000, help="porta di partenza (default 8000)")
    serve.add_argument("--no-browser", action="store_true", help="non aprire il browser")
    serve.add_argument(
        "--resta-aperto",
        action="store_true",
        help="non fermarsi quando la pagina viene chiusa",
    )
    args = parser.parse_args(argv)

    if args.comando is None:
        parser.print_help()
        return 0

    if not args.resta_aperto:
        os.environ[watchdog.VARIABILE] = "1"

    port = free_port(args.port)
    url = f"http://127.0.0.1:{port}"
    print(f"Ricerca in ascolto su {url}  (Ctrl-C per fermare)")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run("ricerca.app:app", host="127.0.0.1", port=port, log_level="info")
    return 0
