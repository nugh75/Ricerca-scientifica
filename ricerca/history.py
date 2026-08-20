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
from .models import Filtri, SourceResult, Strategy, Work

MAX_VOCI = 50


NOME_FILE = "history.json"
NOME_STORICO = "cronologia.json"


def _percorso() -> Path:
    """Il file della cronologia, traslocando quello col nome vecchio."""

    percorso = config_module.CONFIG_DIR / NOME_FILE
    storico = config_module.CONFIG_DIR / NOME_STORICO
    if storico.exists() and not percorso.exists():
        storico.rename(percorso)
    return percorso


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
        "filtri": asdict(strategy.filtri),
        "fonti": _statistiche(results, works),
        "totale": len(works),
        "record": [asdict(w) for w in works],
    }
    _scrivi([voce] + _leggi())
    return voce["id"]


def aggiungi(id_voce: str, nuovi: list[Work], etichetta: str) -> int:
    """Attacca record nuovi a una ricerca già fatta, in coda e senza doppioni.

    In coda perché le decisioni di screening sono indicizzate per posizione:
    inserire in mezzo le sposterebbe tutte sul record sbagliato. La
    provenienza sostituisce quella della fonte, così nel protocollo si vede
    che sono arrivati dallo snowballing e non dalla query.
    """

    from .dedup import _key

    voci = _leggi()
    for voce_corrente in voci:
        if voce_corrente.get("id") != id_voce:
            continue
        presenti = {_key(Work(**_campi(r))) for r in voce_corrente.get("record", [])}
        entrati = 0
        for work in nuovi:
            if _key(work) in presenti:
                continue
            presenti.add(_key(work))
            work.sources = [etichetta]
            voce_corrente.setdefault("record", []).append(asdict(work))
            entrati += 1
        voce_corrente["totale"] = len(voce_corrente.get("record", []))
        _scrivi(voci)
        return entrati
    return 0


def _campi(record_salvato: dict) -> dict:
    """Solo le chiavi che `Work` conosce: una cronologia vecchia può averne
    di più o di meno di quelle del programma di oggi."""

    ammessi = set(Work.__dataclass_fields__)
    return {k: v for k, v in record_salvato.items() if k in ammessi}


def _statistiche(results: list[SourceResult], works: list[Work]) -> list[dict]:
    from .search import statistiche

    return statistiche(results, works)


def elenco() -> list[dict]:
    """Le voci senza i record: per la pagina della cronologia basta il resto."""

    return [{k: v for k, v in voce.items() if k != "record"} for voce in _leggi()]


def voce(id_voce: str) -> dict | None:
    return next((v for v in _leggi() if v.get("id") == id_voce), None)


def record(id_voce: str) -> list[Work]:
    from .sources.base import testo

    trovata = voce(id_voce)
    if not trovata:
        return []
    prese = trovata.get("decisioni", {})
    corrette = trovata.get("correzioni", {})
    completate = trovata.get("completamenti", {})
    lavori = []
    for indice, dati in enumerate(trovata.get("record", [])):
        lavoro = Work(**dati)
        # Le cronologie precedenti alla pulizia degli abstract possono ancora
        # contenere tag JATS/HTML. Ripulirli in lettura risana anche quei dati
        # senza riscrivere il file storico dell'utente.
        lavoro.abstract = testo(lavoro.abstract)
        decisione = prese.get(str(indice), {})
        lavoro.decisione = decisione.get("stato", "")
        lavoro.motivo = decisione.get("motivo", "")
        # Prima ciò che mancava, poi ciò che è stato corretto a mano: la
        # correzione dell'utente vince sempre sul completamento automatico.
        for campo, valore in completate.get(str(indice), {}).items():
            if hasattr(lavoro, campo):
                setattr(lavoro, campo, valore)
                lavoro.completato.append(campo)
        for campo, valore in corrette.get(str(indice), {}).items():
            if hasattr(lavoro, campo):
                setattr(lavoro, campo, valore)
                lavoro.corretto.append(campo)
                if campo in lavoro.completato:
                    lavoro.completato.remove(campo)
        lavori.append(lavoro)
    return lavori


CAMPI_CORREGGIBILI = ("title", "authors", "year", "venue", "doi")


def correggi(id_voce: str, indice: int, campi: dict) -> dict:
    """Salva una correzione a mano. L'originale resta dov'è.

    Le banche dati sbagliano: un anno di stampa al posto di quello di
    pubblicazione, un autore attaccato al precedente. Correggerlo migliora
    `.bib` e riferimenti APA, ma il dato d'origine non si tocca.
    """

    voci = _leggi()
    for voce_corrente in voci:
        if voce_corrente.get("id") != id_voce:
            continue
        originali = voce_corrente.get("record", [])
        if indice >= len(originali):
            return {}
        correzioni_voce = voce_corrente.setdefault("correzioni", {})
        chiave = str(indice)
        attuali = correzioni_voce.get(chiave, {})
        for campo, valore in campi.items():
            if campo not in CAMPI_CORREGGIBILI:
                continue
            if valore in (None, "", []) or valore == originali[indice].get(campo):
                attuali.pop(campo, None)     # tornato all'originale: non è più una correzione
            else:
                attuali[campo] = valore
        if attuali:
            correzioni_voce[chiave] = attuali
        else:
            correzioni_voce.pop(chiave, None)
        _scrivi(voci)
        return attuali
    return {}


def completa(id_voce: str, indice: int, campi: dict) -> dict:
    """Registra i campi trovati da Unpaywall per un record."""

    voci = _leggi()
    for voce_corrente in voci:
        if voce_corrente.get("id") != id_voce:
            continue
        completamenti = voce_corrente.setdefault("completamenti", {})
        attuali = completamenti.setdefault(str(indice), {})
        attuali.update({c: v for c, v in campi.items() if v})
        if not attuali:
            completamenti.pop(str(indice), None)
        _scrivi(voci)
        return attuali
    return {}


def salva_sintesi(id_voce: str, indice: int, sintesi: dict) -> dict:
    """Il riassunto resta con il record: si scrive una volta e si rilegge."""

    voci = _leggi()
    for voce_corrente in voci:
        if voce_corrente.get("id") != id_voce:
            continue
        sintesi_voce = voce_corrente.setdefault("sintesi", {})
        sintesi_voce[str(indice)] = sintesi
        _scrivi(voci)
        return sintesi
    return {}


def sintesi(id_voce: str, indice: int) -> dict:
    return (voce(id_voce) or {}).get("sintesi", {}).get(str(indice), {})


def originale(id_voce: str, indice: int) -> Work | None:
    """Il record come è arrivato dalle banche dati, senza correzioni."""

    trovata = voce(id_voce) or {}
    dati = trovata.get("record", [])
    return Work(**dati[indice]) if indice < len(dati) else None


def strategia(id_voce: str) -> Strategy:
    from .models import Block

    trovata = voce(id_voce) or {}
    blocchi = [Block(**b) for b in trovata.get("blocchi", [])]
    return Strategy(blocks=blocchi, mesh=list(trovata.get("mesh", [])))


def filtri(id_voce: str) -> Filtri:
    """I filtri di una ricerca salvata. Una voce vecchia non li ha: niente
    filtri è la risposta giusta, non un errore."""

    salvati = (voce(id_voce) or {}).get("filtri") or {}
    ammessi = set(Filtri.__dataclass_fields__)
    return Filtri(**{k: v for k, v in salvati.items() if k in ammessi})


STATI = ("incluso", "forse", "escluso")


def decide(id_voce: str, indice: int, stato: str, motivo: str = "") -> dict:
    """Registra la decisione di screening su un record. Ripetere annulla."""

    voci = _leggi()
    for voce_corrente in voci:
        if voce_corrente.get("id") != id_voce:
            continue
        decisioni = voce_corrente.setdefault("decisioni", {})
        chiave = str(indice)
        if stato not in STATI or decisioni.get(chiave, {}).get("stato") == stato:
            decisioni.pop(chiave, None)
        else:
            decisioni[chiave] = {"stato": stato, "motivo": motivo.strip()}
        _scrivi(voci)
        return decisioni
    return {}


def decisioni(id_voce: str) -> dict:
    return (voce(id_voce) or {}).get("decisioni", {})


def conteggi(id_voce: str) -> dict:
    """I numeri che servono al diagramma di flusso PRISMA."""

    trovata = voce(id_voce) or {}
    prese = trovata.get("decisioni", {}).values()
    conta = {stato: sum(1 for d in prese if d.get("stato") == stato) for stato in STATI}
    grezzi = sum(f.get("trovati", 0) for f in trovata.get("fonti", []))
    conta["grezzi"] = grezzi
    conta["dopo_deduplica"] = trovata.get("totale", 0)
    conta["duplicati"] = max(grezzi - trovata.get("totale", 0), 0)
    conta["da_valutare"] = trovata.get("totale", 0) - sum(conta[s] for s in STATI)
    return conta


def elimina(id_voce: str) -> bool:
    voci = _leggi()
    restanti = [v for v in voci if v.get("id") != id_voce]
    if len(restanti) == len(voci):
        return False
    _scrivi(restanti)
    return True


def svuota() -> None:
    _scrivi([])
