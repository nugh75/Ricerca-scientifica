"""Ricerca — assistente di strategia di ricerca bibliografica."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ricerca")
except PackageNotFoundError:  # eseguito dal sorgente, senza installazione
    __version__ = "0.0.0+sorgente"
