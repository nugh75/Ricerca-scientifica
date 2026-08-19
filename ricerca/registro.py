"""Registro di quel che l'app sta facendo, e di quel che va storto.

Due destinazioni: una lista in memoria, che la pagina mostra, e un file in
~/.ricerca/attivita.log, che resta anche se il processo muore — è lì che si
guarda quando qualcosa cade in silenzio.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from . import config as config_module

MASSIMO_IN_MEMORIA = 200
MASSIMO_FILE_BYTE = 1_000_000
NOME_FILE = "attivita.log"

_serratura = threading.Lock()
_voci: deque = deque(maxlen=MASSIMO_IN_MEMORIA)


@dataclass
class Voce:
    quando: str
    livello: str          # "info" oppure "errore"
    azione: str           # che cosa stava facendo
    dettaglio: str        # com'è andata

    @property
    def errore(self) -> bool:
        return self.livello == "errore"


def _scrivi_su_file(voce: Voce) -> None:
    try:
        percorso = config_module.CONFIG_DIR / NOME_FILE
        percorso.parent.mkdir(parents=True, exist_ok=True)
        if percorso.exists() and percorso.stat().st_size > MASSIMO_FILE_BYTE:
            coda = percorso.read_text(encoding="utf-8", errors="replace")[-MASSIMO_FILE_BYTE // 2 :]
            percorso.write_text(coda, encoding="utf-8")
        with percorso.open("a", encoding="utf-8") as file:
            file.write(f"{voce.quando}\t{voce.livello}\t{voce.azione}\t{voce.dettaglio}\n")
    except OSError:
        pass  # un registro che non si scrive non deve fermare l'app


def annota(azione: str, dettaglio: str = "", livello: str = "info") -> Voce:
    voce = Voce(
        quando=datetime.now().strftime("%H:%M:%S"),
        livello="errore" if livello == "errore" else "info",
        azione=str(azione)[:120],
        dettaglio=" ".join(str(dettaglio).split())[:300],
    )
    with _serratura:
        _voci.append(voce)
    _scrivi_su_file(voce)
    return voce


def errore(azione: str, dettaglio: str = "") -> Voce:
    return annota(azione, dettaglio, livello="errore")


def ultime(quante: int = 40) -> list[Voce]:
    with _serratura:
        return list(_voci)[-quante:][::-1]


def quanti_errori() -> int:
    with _serratura:
        return sum(1 for voce in _voci if voce.errore)


def svuota() -> None:
    with _serratura:
        _voci.clear()


def come_testo() -> str:
    with _serratura:
        righe = list(_voci)
    return "\n".join(f"{v.quando}\t{v.livello}\t{v.azione}\t{v.dettaglio}" for v in righe) + "\n"
