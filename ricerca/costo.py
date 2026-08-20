"""Contabilità del credito OpenAlex, giorno per giorno.

OpenAlex dichiara in ogni risposta quanto è costata (`meta.cost_usd`) e taglia
il servizio quando il budget quotidiano finisce: $1.00 con la chiave gratuita,
$0.10 senza. Tenerne il conto qui evita di scoprire il limite con un `429` a
metà di una ricerca.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from . import config as config_module
from .config import Config

BUDGET_CON_CHIAVE = 1.00
BUDGET_SENZA_CHIAVE = 0.10
COSTO_PDF = 0.01          # l'archivio non dichiara il costo nel corpo
GIORNI_TENUTI = 30
NOME_FILE = "openalex-costo.json"


def oggi() -> str:
    return date.today().isoformat()


def _percorso() -> Path:
    return config_module.CONFIG_DIR / NOME_FILE


def _leggi() -> dict[str, float]:
    percorso = _percorso()
    if not percorso.exists():
        return {}
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}  # un registro rotto non deve fermare una ricerca
    if not isinstance(dati, dict):
        return {}
    return {str(k): float(v) for k, v in dati.items() if isinstance(v, (int, float))}


def aggiungi(usd: float, quando: str = "") -> float:
    """Somma una spesa alla giornata e restituisce il totale di quel giorno."""

    giorno = quando or oggi()
    if usd <= 0:
        return speso(giorno)
    dati = _leggi()
    dati[giorno] = round(dati.get(giorno, 0.0) + usd, 6)
    recenti = dict(sorted(dati.items())[-GIORNI_TENUTI:])
    percorso = _percorso()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    try:
        percorso.write_text(json.dumps(recenti, indent=1), encoding="utf-8")
    except OSError:
        pass
    return recenti[giorno]


def speso(quando: str = "") -> float:
    return _leggi().get(quando or oggi(), 0.0)


def budget(config: Config) -> float:
    return BUDGET_CON_CHIAVE if config.openalex_api_key else BUDGET_SENZA_CHIAVE


def resta(config: Config) -> float:
    return max(0.0, round(budget(config) - speso(), 4))
