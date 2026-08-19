"""Chiusura automatica quando nessuna pagina è più aperta.

La pagina manda un battito ogni pochi secondi e un ultimo segnale quando
viene chiusa. Se i battiti smettono di arrivare, il server si ferma da solo:
chi lancia l'app dal Finder o da un'icona non ha un terminale dove premere
Ctrl-C.

Attiva solo quando l'avvio passa da `ricerca serve` (variabile
RICERCA_AUTOCHIUSURA): con uvicorn a mano, o nei test, resta spenta.
"""

from __future__ import annotations

import asyncio
import os
import signal
import time

VARIABILE = "RICERCA_AUTOCHIUSURA"

# Il battito arriva ogni 4 secondi, ma i browser rallentano i timer delle
# finestre in secondo piano fino a uno al minuto: sotto i 90 secondi si
# rischia di spegnere l'app mentre l'utente sta solo guardando altrove.
SILENZIO_MASSIMO = 90.0
# Dopo il segnale di chiusura si concede una pausa: un ricaricamento della
# pagina manda subito un nuovo battito e annulla lo spegnimento.
ATTESA_DOPO_CHIUSURA = 5.0
INTERVALLO_CONTROLLO = 2.0


class Sorveglianza:
    def __init__(self):
        self.ultimo_battito = time.monotonic()
        self.mai_vista_una_pagina = True
        self.scadenza: float | None = None
        self.richieste_in_corso = 0
        self.lavori_in_corso = lambda: 0

    def apre_una_richiesta(self) -> None:
        self.richieste_in_corso += 1

    def chiude_una_richiesta(self) -> None:
        self.richieste_in_corso = max(0, self.richieste_in_corso - 1)
        self.ultimo_battito = time.monotonic()

    def sta_lavorando(self) -> bool:
        return self.richieste_in_corso > 0 or self.lavori_in_corso() > 0

    def battito(self) -> None:
        self.ultimo_battito = time.monotonic()
        self.mai_vista_una_pagina = False
        self.scadenza = None

    def pagina_chiusa(self) -> None:
        self.scadenza = time.monotonic() + ATTESA_DOPO_CHIUSURA

    def deve_fermarsi(self, adesso: float | None = None) -> bool:
        adesso = time.monotonic() if adesso is None else adesso
        if self.mai_vista_una_pagina:
            return False
        # Non si spegne mai mentre sta facendo qualcosa: una ricerca lunga
        # verrebbe interrotta a metà e sembrerebbe fallita.
        if self.sta_lavorando():
            return False
        if self.scadenza is not None and adesso >= self.scadenza:
            return True
        return adesso - self.ultimo_battito > SILENZIO_MASSIMO


stato = Sorveglianza()


def attiva() -> bool:
    return os.environ.get(VARIABILE) == "1"


async def sorveglia(ferma=None) -> None:
    """Controlla i battiti e ferma il processo quando non ne arrivano più."""

    ferma = ferma or (lambda: os.kill(os.getpid(), signal.SIGTERM))
    while True:
        await asyncio.sleep(INTERVALLO_CONTROLLO)
        if stato.deve_fermarsi():
            ferma()
            return
