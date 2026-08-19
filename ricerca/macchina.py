"""Che cosa regge questo computer, e quale modello locale conviene.

Serve alla configurazione guidata: consigliare «qwen3:8b» a chi ha 8 GB di
memoria e a chi ne ha 64 è un modo sicuro per far sembrare i modelli locali
inutilizzabili.
"""

from __future__ import annotations

import ctypes
import os
import platform
from dataclasses import dataclass

GIGA = 1024**3


@dataclass
class Modello:
    nome: str
    peso: str
    # Chiave di traduzione: il motivo va scritto nella lingua dell'interfaccia.
    motivo: str


def memoria_gb() -> float | None:
    """Memoria installata, per quel che il sistema lascia sapere."""

    try:
        if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names:
            return round(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / GIGA, 1)
    except (ValueError, OSError):
        pass
    if platform.system() == "Windows":
        try:

            class Stato(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stato = Stato()
            stato.dwLength = ctypes.sizeof(Stato)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stato))
            return round(stato.ullTotalPhys / GIGA, 1)
        except (AttributeError, OSError):
            return None
    return None


def apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64")


def descrizione() -> dict:
    return {
        "sistema": platform.system(),
        "processori": os.cpu_count() or 0,
        "memoria_gb": memoria_gb(),
        "apple_silicon": apple_silicon(),
    }


# Distingue «non me lo dire, guardalo tu» da «non si sa quanta memoria c'è».
RILEVA = object()


def consiglio(memoria=RILEVA, silicio_apple=RILEVA) -> list[Modello]:
    """Modelli Ollama sensati per questa macchina, dal più prudente in su.

    Pesi verificati nel registro di Ollama il 2026-08-19. La regola pratica:
    al modello va lasciata memoria libera almeno pari al suo peso, e al
    sistema il resto. I tagli `-qat` di Gemma sono quantizzati dagli autori:
    stessa famiglia, molta meno memoria.
    """

    memoria = memoria_gb() if memoria is RILEVA else memoria
    silicio_apple = apple_silicon() if silicio_apple is RILEVA else silicio_apple

    if memoria is None:
        return [Modello("gemma4:e2b-it-qat", "4,3 GB", "reason_unknown")]
    if memoria < 8:
        return [
            Modello("qwen3:1.7b", "1,4 GB", "reason_low_memory"),
            Modello("gemma4:e2b-it-qat", "4,3 GB", "reason_step_up"),
        ]
    if memoria < 16:
        return [
            Modello("gemma4:e2b-it-qat", "4,3 GB", "reason_fast"),
            Modello("gemma4:e4b-it-qat", "6,1 GB", "reason_better"),
        ]
    if memoria < 32:
        return [
            Modello("gemma4:12b-it-qat", "7,2 GB", "reason_balanced"),
            Modello("gemma4:12b", "7,6 GB", "reason_precise"),
        ]
    # Da qui in su regge qwen3.8, che è il più capace della lista.
    prima = (
        Modello("qwen3.8:27b-mlx", "18 GB", "reason_big_mac")
        if silicio_apple
        else Modello("qwen3.8:27b", "18 GB", "reason_big_gpu")
    )
    return [prima, Modello("gemma4:26b-a4b-it-qat", "16 GB", "reason_comfortable")]


def limite_consigliato(memoria=RILEVA) -> int:
    """Quanti record per fonte chiedere senza appesantire questa macchina.

    Ogni record diventa una riga con i suoi comandi: su una macchina modesta
    duecento righe si sentono nello scorrimento.
    """

    memoria = memoria_gb() if memoria is RILEVA else memoria
    if memoria is None:
        return 25
    if memoria < 8:
        return 15
    if memoria < 16:
        return 25
    return 50
