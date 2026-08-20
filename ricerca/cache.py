"""Cache locale delle risposte HTTP, in SQLite sotto ~/.ricerca.

Ripetere la stessa query è normale mentre si affina una strategia: senza
cache si ribatte sulle API e si finisce nei limiti di richiesta (`429`).

È un trasporto httpx: le fonti non se ne accorgono. Si spegne con
RICERCA_CACHE=0 (i test lo fanno, per non falsare i conteggi di chiamata).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time

import httpx

from . import config as config_module

DURATA = 24 * 60 * 60  # un giorno
VARIABILE = "RICERCA_CACHE"
# Le risposte servite dalla cache portano questo marcatore: il costo OpenAlex
# si conta una volta sola, non a ogni ripetizione della stessa query.
INTESTAZIONE = "x-ricerca-cache"


def attiva() -> bool:
    return os.environ.get(VARIABILE, "1") != "0"


def _percorso():
    cartella = config_module.CONFIG_DIR
    cartella.mkdir(parents=True, exist_ok=True)
    return cartella / "cache.sqlite"


def _connessione() -> sqlite3.Connection:
    conn = sqlite3.connect(_percorso())
    conn.execute(
        "CREATE TABLE IF NOT EXISTS risposte "
        "(chiave TEXT PRIMARY KEY, quando REAL, stato INTEGER, tipo TEXT, corpo BLOB)"
    )
    return conn


def chiave(request: httpx.Request) -> str:
    return hashlib.sha256(f"{request.method} {request.url}".encode("utf-8")).hexdigest()


def leggi(chiave_richiesta: str, durata: float = DURATA):
    try:
        with _connessione() as conn:
            riga = conn.execute(
                "SELECT quando, stato, tipo, corpo FROM risposte WHERE chiave = ?",
                (chiave_richiesta,),
            ).fetchone()
    except sqlite3.Error:
        return None
    if riga is None or time.time() - riga[0] > durata:
        return None
    return riga[1], riga[2], riga[3]


def scrivi(chiave_richiesta: str, stato: int, tipo: str, corpo: bytes) -> None:
    try:
        with _connessione() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO risposte VALUES (?, ?, ?, ?, ?)",
                (chiave_richiesta, time.time(), stato, tipo, corpo),
            )
    except sqlite3.Error:
        pass  # la cache è un lusso: se non si può scrivere, si prosegue


def svuota() -> None:
    try:
        with _connessione() as conn:
            conn.execute("DELETE FROM risposte")
    except sqlite3.Error:
        pass


def _intestazioni(risposta: httpx.Response) -> dict:
    """Il corpo è già decompresso: tenere `content-encoding` farebbe
    ritentare la decompressione al chiamante («incorrect header check»)."""

    saltate = {"content-encoding", "content-length", "transfer-encoding"}
    return {k: v for k, v in risposta.headers.items() if k.lower() not in saltate}


class TrasportoConCache(httpx.AsyncHTTPTransport):
    """Serve dalla cache le GET già viste; le altre passano oltre."""

    def __init__(self, durata: float = DURATA, **kwargs):
        super().__init__(**kwargs)
        self.durata = durata

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if not attiva() or request.method != "GET":
            return await super().handle_async_request(request)

        chiave_richiesta = chiave(request)
        salvata = leggi(chiave_richiesta, self.durata)
        if salvata is not None:
            stato, tipo, corpo = salvata
            return httpx.Response(
                stato, content=corpo, headers={"content-type": tipo, INTESTAZIONE: "1"}
            )

        risposta = await super().handle_async_request(request)
        if risposta.status_code == 200:
            corpo = await risposta.aread()
            scrivi(
                chiave_richiesta,
                risposta.status_code,
                risposta.headers.get("content-type", "application/json"),
                corpo,
            )
            return httpx.Response(risposta.status_code, content=corpo, headers=_intestazioni(risposta))
        return risposta


def client(**kwargs) -> httpx.AsyncClient:
    """Un client httpx con la cache già montata."""

    return httpx.AsyncClient(transport=TrasportoConCache(), **kwargs)
