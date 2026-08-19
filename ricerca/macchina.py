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

    La regola pratica: un modello quantizzato occupa all'incirca un gigabyte
    ogni miliardo di parametri, e sotto va lasciata memoria al sistema.
    """

    memoria = memoria_gb() if memoria is RILEVA else memoria
    silicio_apple = apple_silicon() if silicio_apple is RILEVA else silicio_apple

    if memoria is None:
        return [
            Modello("qwen3:4b", "~3 GB", "reason_unknown"),
        ]
    if memoria < 8:
        return [
            Modello("qwen3:1.7b", "~1,4 GB", "reason_low_memory"),
            Modello("llama3.2:3b", "~2 GB", "reason_step_up"),
        ]
    if memoria < 16:
        return [
            Modello("qwen3:4b", "~3 GB", "reason_fast"),
            Modello("llama3.1:8b", "~5 GB", "reason_better"),
        ]
    if memoria < 32:
        return [
            Modello("qwen3:8b", "~5 GB", "reason_balanced"),
            Modello("gemma3:12b", "~8 GB", "reason_precise"),
        ]
    prima = Modello("qwen3:14b", "~9 GB", "reason_comfortable")
    seconda = (
        Modello("qwen3:30b-a3b", "~18 GB", "reason_big_mac")
        if silicio_apple
        else Modello("gpt-oss:20b", "~13 GB", "reason_big_gpu")
    )
    return [prima, seconda]
