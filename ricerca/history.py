"""Cronologia delle ricerche, in un file JSON sotto ~/.ricerca.

Ogni voce conserva la strategia, l'esito per fonte e i record trovati: basta
per riaprire una ricerca, riesportarla o scaricarne i PDF senza ripeterla.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from . import config as config_module
from .models import SourceResult, Strategy, Work

MAX_VOCI = 50


def _percorso() -> Path:
    return config_module.CONFIG_DIR / "cronologia.json"


def _leggi() -> list[dict]:
    path = _percorso()
    if not path.exists():
        return []
    try:
        dati = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return dati if isinstance(dati, list) else []


def _scrivi(voci: list[dict]) -> None:
    path = _percorso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(voci[:MAX_VOCI], ensure_ascii=False, indent=1), encoding="utf-8")
    path.chmod(0o600)


def salva(
    topic: str, strategy: Strategy, results: list[SourceResult], works: list[Work]
) -> str:
    voce = {
        "id": secrets.token_urlsafe(8),
        "quando": datetime.now().isoformat(timespec="seconds"),
        "topic": topic,
        "blocchi": [asdict(b) for b in strategy.blocks],
        "mesh": list(strategy.mesh),
        "fonti": [
            {
                "id": r.source_id,
                "etichetta": r.label,
                "query": r.query,
                "trovati": len(r.works),
                "errore": r.error,
            }
            for r in results
        ],
        "totale": len(works),
        "record": [asdict(w) for w in works],
    }
    _scrivi([voce] + _leggi())
    return voce["id"]


def elenco() -> list[dict]:
    """Le voci senza i record: per la pagina della cronologia basta il resto."""

    return [{k: v for k, v in voce.items() if k != "record"} for voce in _leggi()]


def voce(id_voce: str) -> dict | None:
    return next((v for v in _leggi() if v.get("id") == id_voce), None)


def record(id_voce: str) -> list[Work]:
    trovata = voce(id_voce)
    if not trovata:
        return []
    return [Work(**dati) for dati in trovata.get("record", [])]


def strategia(id_voce: str) -> Strategy:
    from .models import Block

    trovata = voce(id_voce) or {}
    blocchi = [Block(**b) for b in trovata.get("blocchi", [])]
    return Strategy(blocks=blocchi, mesh=list(trovata.get("mesh", [])))


def elimina(id_voce: str) -> bool:
    voci = _leggi()
    restanti = [v for v in voci if v.get("id") != id_voce]
    if len(restanti) == len(voci):
        return False
    _scrivi(restanti)
    return True


def svuota() -> None:
    _scrivi([])
