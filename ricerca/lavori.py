"""Operazioni che proseguono anche se si cambia pagina.

Una ricerca su otto banche dati, o lo scaricamento di trenta PDF, dura più
di quanto una persona resti ferma a guardare. Il lavoro parte sul server e
continua da solo: la pagina lo interroga finché serve, e chi torna dopo lo
ritrova finito.
"""

from __future__ import annotations

import asyncio
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .config import load as carica_config
from .i18n import strings
from .registro import annota, errore

# I lavori conclusi restano a disposizione per un po', poi si tolgono di mezzo.
DURATA_RICORDO = 30 * 60


@dataclass
class Lavoro:
    id: str
    descrizione: str
    stato: str = "in corso"        # in corso | finito | fallito
    avvio: float = field(default_factory=time.monotonic)
    risultato: Any = None
    errore: str = ""

    @property
    def finito(self) -> bool:
        return self.stato != "in corso"

    @property
    def secondi(self) -> float:
        return round(time.monotonic() - self.avvio, 1)


_lavori: dict[str, Lavoro] = {}
_compiti: dict[str, Any] = {}

# I lavori girano su un ciclo di eventi tutto loro, in un filo separato:
# legati al ciclo della richiesta verrebbero annullati appena la pagina
# riceve risposta — cioè proprio quando si cambia pagina.
_ciclo: asyncio.AbstractEventLoop | None = None
_serratura = threading.Lock()


def _ciclo_dei_lavori() -> asyncio.AbstractEventLoop:
    global _ciclo
    with _serratura:
        if _ciclo is None or _ciclo.is_closed():
            _ciclo = asyncio.new_event_loop()
            filo = threading.Thread(
                target=_ciclo.run_forever, name="lavori-ricerca", daemon=True
            )
            filo.start()
        return _ciclo


def _ripulisci() -> None:
    scaduti = [
        chiave
        for chiave, lavoro in _lavori.items()
        if lavoro.finito and time.monotonic() - lavoro.avvio > DURATA_RICORDO
    ]
    for chiave in scaduti:
        _lavori.pop(chiave, None)
        _compiti.pop(chiave, None)


def avvia(coroutine, descrizione: str) -> Lavoro:
    """Mette in moto il lavoro e ritorna subito il suo cartellino."""

    _ripulisci()
    lavoro = Lavoro(id=secrets.token_urlsafe(6), descrizione=descrizione)
    _lavori[lavoro.id] = lavoro
    etichette = strings(carica_config().lang)
    annota(etichette["log_job_started"].format(cosa=descrizione))

    async def esegui():
        try:
            lavoro.risultato = await coroutine
            lavoro.stato = "finito"
            annota(etichette["log_job_done"].format(cosa=descrizione), f"{lavoro.secondi}s")
        except asyncio.CancelledError:
            lavoro.stato = "fallito"
            lavoro.errore = "interrotto"
            errore(etichette["log_job_stopped"].format(cosa=descrizione))
            raise
        except Exception as exc:  # nessun guasto deve restare muto
            lavoro.stato = "fallito"
            lavoro.errore = f"{type(exc).__name__}: {exc}"[:300]
            errore(etichette["log_job_failed"].format(cosa=descrizione), lavoro.errore)

    _compiti[lavoro.id] = asyncio.run_coroutine_threadsafe(esegui(), _ciclo_dei_lavori())
    return lavoro


def prendi(id_lavoro: str) -> Lavoro | None:
    return _lavori.get(id_lavoro)


def per_descrizione(descrizione: str) -> Lavoro | None:
    """Il lavoro in corso su questa cosa, se c'è: evita di avviarlo due volte."""

    for lavoro in _lavori.values():
        if lavoro.descrizione == descrizione and not lavoro.finito:
            return lavoro
    return None


def in_corso() -> list[Lavoro]:
    return [lavoro for lavoro in _lavori.values() if not lavoro.finito]


def attendi(id_lavoro: str, timeout: float = 60) -> Lavoro | None:
    """Blocca finché il lavoro non è concluso. Serve ai test e alla CLI."""

    compito = _compiti.get(id_lavoro)
    if compito is not None:
        compito.result(timeout=timeout)
    return prendi(id_lavoro)


def svuota() -> None:
    _lavori.clear()
    _compiti.clear()
