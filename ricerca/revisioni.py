"""Workspace locali per revisioni della letteratura.

La cronologia conserva le singole interrogazioni. Questo modulo le raccoglie
in progetti più lunghi, senza modificarle: il corpus del progetto è una copia
stabile con provenienza, decisioni e audit trail propri.
"""

from __future__ import annotations

import json
import re
import secrets
import unicodedata
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config as config_module
from . import history
from .dedup import _key
from .models import Work


NOME_FILE = "reviews.json"
TIPI = ("sistematica", "scoping", "narrativa")
FASI_SCREENING = ("abstract", "fulltext")
STATI = ("incluso", "forse", "escluso")
STATI_TESTO_COMPLETO = ("da_reperire", "richiesto", "disponibile", "non_disponibile")

CAMPI_PROTOCOLLO = (
    "domanda", "framework", "popolazione", "concetto", "intervento",
    "comparatore", "outcome", "contesto", "disegni", "criteri_inclusione",
    "criteri_esclusione", "fonti_previste", "piano_sintesi", "registrazione",
    "frequenza_aggiornamento", "peer_review_strategia", "articoli_sentinella",
)

CAMPI_ESTRAZIONE = (
    "disegno", "popolazione", "intervento", "comparatore", "outcome",
    "risultati", "nota", "pagina",
)

CAMPI_BIAS = (
    "strumento", "giudizio", "domini", "motivazione", "evidenza", "pagina",
)

CAMPI_EVIDENZA = (
    "outcome", "studi", "partecipanti", "effetto", "certezza", "motivazione",
)


def _percorso() -> Path:
    return config_module.CONFIG_DIR / NOME_FILE


def _adesso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _leggi() -> list[dict]:
    path = _percorso()
    if not path.exists():
        return []
    try:
        dati = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return dati if isinstance(dati, list) else []


def _scrivi(progetti: list[dict]) -> None:
    path = _percorso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(progetti, ensure_ascii=False, indent=1), encoding="utf-8")
    path.chmod(0o600)


def _evento(progetto: dict, azione: str, dettaglio: str = "") -> None:
    progetto.setdefault("registro", []).append(
        {"quando": _adesso(), "azione": azione, "dettaglio": dettaglio.strip()}
    )
    progetto["aggiornato"] = _adesso()


def _modifica(id_progetto: str, funzione):
    progetti = _leggi()
    for progetto_corrente in progetti:
        if progetto_corrente.get("id") != id_progetto:
            continue
        risultato = funzione(progetto_corrente)
        _scrivi(progetti)
        return risultato
    return None


def crea(titolo: str, tipo: str = "sistematica", revisori: list[str] | None = None) -> str:
    tipo = tipo if tipo in TIPI else "sistematica"
    nomi = []
    for nome in revisori or []:
        nome = nome.strip()
        if nome and nome.casefold() not in {n.casefold() for n in nomi}:
            nomi.append(nome)
    quando = _adesso()
    progetto_nuovo = {
        "id": secrets.token_urlsafe(8),
        "titolo": titolo.strip() or "Review senza titolo",
        "tipo": tipo,
        "creato": quando,
        "aggiornato": quando,
        "revisori": nomi or ["Revisore 1"],
        "protocollo": {},
        "emendamenti": [],
        "ricerche": [],
        "record": [],
        "decisioni": {},
        "consenso": {},
        "testi_completi": {},
        "gruppi_studio": {},
        "versioni_record": {},
        "estrazioni": {},
        "consenso_estrazioni": {},
        "bias": {},
        "evidenze": [],
        "wiki": {},
        "aggiornamenti": [],
        "registro": [],
    }
    _evento(progetto_nuovo, "progetto creato", tipo)
    _scrivi([progetto_nuovo, *_leggi()])
    return progetto_nuovo["id"]


def rinomina(id_progetto: str, titolo: str) -> bool:
    """Cambia il titolo di un progetto già avviato.

    Il titolo di una revisione si assesta lavorandoci: quello scelto il primo
    giorno raramente è quello che finisce nel report. Cambia solo l'etichetta
    — id, corpus, decisioni e registro restano dove sono.
    """

    titolo = titolo.strip()
    if not titolo:
        return False

    def applica(progetto_corrente: dict):
        precedente = progetto_corrente.get("titolo", "")
        if precedente == titolo:
            return False
        progetto_corrente["titolo"] = titolo
        _evento(progetto_corrente, "progetto rinominato", f"«{precedente}» → «{titolo}»")
        return True

    return bool(_modifica(id_progetto, applica))


def elenco() -> list[dict]:
    return [
        {
            **p,
            "totale_record": len(p.get("record", [])),
            "record": [], "decisioni": {}, "estrazioni": {}, "bias": {},
        }
        for p in _leggi()
    ]


def progetto(id_progetto: str) -> dict | None:
    return next((p for p in _leggi() if p.get("id") == id_progetto), None)


def elimina(id_progetto: str) -> bool:
    progetti = _leggi()
    restanti = [p for p in progetti if p.get("id") != id_progetto]
    if len(restanti) == len(progetti):
        return False
    _scrivi(restanti)
    return True


def salva_protocollo(id_progetto: str, dati: dict, motivo: str = "") -> dict:
    puliti = {campo: str(dati.get(campo, "")).strip() for campo in CAMPI_PROTOCOLLO}

    def applica(progetto_corrente: dict):
        precedente = progetto_corrente.get("protocollo", {})
        cambiati = {
            campo: {"prima": precedente.get(campo, ""), "dopo": valore}
            for campo, valore in puliti.items()
            if precedente.get(campo, "") != valore
        }
        if precedente and cambiati:
            progetto_corrente.setdefault("emendamenti", []).append({
                "quando": _adesso(),
                "motivo": motivo.strip() or "Modifica del protocollo",
                "campi": cambiati,
            })
        progetto_corrente["protocollo"] = puliti
        _evento(progetto_corrente, "protocollo salvato", ", ".join(cambiati))
        return puliti

    return _modifica(id_progetto, applica) or {}


def campi_protocollo_mancanti(progetto_corrente: dict) -> list[str]:
    protocollo = progetto_corrente.get("protocollo", {})
    richiesti = [
        "domanda", "framework", "popolazione", "concetto",
        "criteri_inclusione", "criteri_esclusione", "fonti_previste",
        "piano_sintesi",
    ]
    if progetto_corrente.get("tipo") == "sistematica":
        richiesti.append("outcome")
    if progetto_corrente.get("tipo") == "scoping":
        richiesti.append("contesto")
    return [campo for campo in richiesti if not str(protocollo.get(campo, "")).strip()]


def collega_ricerca(id_progetto: str, id_ricerca: str) -> int:
    voce = history.voce(id_ricerca)
    if not voce:
        return 0
    lavori = history.record(id_ricerca)

    def applica(progetto_corrente: dict):
        ricerche = progetto_corrente.setdefault("ricerche", [])
        if not any(r.get("id") == id_ricerca for r in ricerche):
            ricerche.append({
                "id": id_ricerca,
                "topic": voce.get("topic", ""),
                "quando": voce.get("quando", ""),
                "fonti": [f.get("etichetta", "") for f in voce.get("fonti", [])],
                "interrogazioni": [
                    {
                        "fonte": f.get("etichetta", ""), "query": f.get("query", ""),
                        "oql": f.get("oql", ""), "trovati": f.get("trovati", 0),
                    }
                    for f in voce.get("fonti", [])
                ],
                "blocchi": voce.get("blocchi", []),
                "mesh": voce.get("mesh", []),
                "filtri": voce.get("filtri", {}),
            })
        record = progetto_corrente.setdefault("record", [])
        per_chiave = {
            _key(Work(**_campi_work(item.get("record", {})))): item for item in record
        }
        aggiunti = 0
        for indice, lavoro in enumerate(lavori):
            chiave = _key(lavoro)
            provenienza = {"ricerca": id_ricerca, "indice": indice}
            if chiave in per_chiave:
                origini = per_chiave[chiave].setdefault("provenienze", [])
                if provenienza not in origini:
                    origini.append(provenienza)
                continue
            item = {
                "id": secrets.token_urlsafe(7),
                "record": asdict(lavoro),
                "provenienze": [provenienza],
            }
            record.append(item)
            per_chiave[chiave] = item
            aggiunti += 1
        _evento(progetto_corrente, "ricerca collegata", f"{id_ricerca}: {aggiunti} nuovi")
        return aggiunti

    risultato = _modifica(id_progetto, applica)
    return int(risultato or 0)


def aggiungi_record(id_progetto: str, id_ricerca: str, indice: int) -> bool:
    """Porta un solo record nel corpus, con la sua provenienza.

    Chi trova tre articoli buoni dentro duecento non deve collegare l'intera
    ricerca per averli: la deduplica è la stessa, e un record già presente
    guadagna una provenienza in più invece di un doppione.
    """

    lavori_salvati = history.record(id_ricerca)
    if not 0 <= indice < len(lavori_salvati):
        return False
    lavoro = lavori_salvati[indice]

    def applica(progetto_corrente: dict):
        record = progetto_corrente.setdefault("record", [])
        provenienza = {"ricerca": id_ricerca, "indice": indice}
        chiave = _key(lavoro)
        for item in record:
            if _key(Work(**_campi_work(item.get("record", {})))) != chiave:
                continue
            origini = item.setdefault("provenienze", [])
            if provenienza not in origini:
                origini.append(provenienza)
            _evento(progetto_corrente, "record già nel corpus", lavoro.title[:60])
            return False
        record.append({
            "id": secrets.token_urlsafe(7),
            "record": asdict(lavoro),
            "provenienze": [provenienza],
        })
        _evento(progetto_corrente, "record aggiunto", lavoro.title[:60])
        return True

    return bool(_modifica(id_progetto, applica))


def scollega_ricerca(id_progetto: str, id_ricerca: str) -> bool:
    """Toglie la ricerca dal workspace senza cancellare il corpus costruito.

    Record, provenienze e decisioni restano: la ricerca salvata può essere
    collegata di nuovo senza perdere il lavoro già svolto.
    """

    def applica(progetto_corrente: dict):
        ricerche = progetto_corrente.setdefault("ricerche", [])
        restanti = [ricerca for ricerca in ricerche if ricerca.get("id") != id_ricerca]
        if len(restanti) == len(ricerche):
            return False
        progetto_corrente["ricerche"] = restanti
        _evento(progetto_corrente, "ricerca scollegata", id_ricerca)
        return True

    return bool(_modifica(id_progetto, applica))


def integra_aggiornamento(id_progetto: str, id_ricerca: str, nuovi_lavori: list[Work]) -> dict:
    """Integra una nuova esecuzione conservando le versioni dei metadati."""

    aggiornabili = (
        "title", "authors", "author_ids", "year", "venue", "venue_id", "url",
        "abstract", "oa_url", "oa_urls", "openalex_id", "ritirato", "citazioni",
        "molto_citato", "pdf_archivio",
    )

    def applica(progetto_corrente: dict):
        record = progetto_corrente.setdefault("record", [])
        per_chiave = {
            _key(Work(**_campi_work(voce.get("record", {})))): voce for voce in record
        }
        quanti = {"nuovi": 0, "modificati": 0, "ritirati": 0}
        for indice, lavoro in enumerate(nuovi_lavori):
            chiave = _key(lavoro)
            provenienza = {"ricerca": id_ricerca, "indice": indice}
            if chiave not in per_chiave:
                nuovo_item = {
                    "id": secrets.token_urlsafe(7),
                    "record": asdict(lavoro),
                    "provenienze": [provenienza],
                }
                record.append(nuovo_item)
                per_chiave[chiave] = nuovo_item
                quanti["nuovi"] += 1
                quanti["ritirati"] += int(lavoro.ritirato)
                continue

            esistente = per_chiave[chiave]
            dati = esistente.setdefault("record", {})
            prima = dict(dati)
            fresco = asdict(lavoro)
            cambiati = []
            for campo in aggiornabili:
                valore = fresco.get(campo)
                if campo in ("ritirato", "molto_citato"):
                    valore = bool(dati.get(campo)) or bool(valore)
                elif valore in (None, "", []):
                    continue
                if dati.get(campo) != valore:
                    dati[campo] = valore
                    cambiati.append(campo)
            dati["sources"] = sorted(set(dati.get("sources", [])) | set(lavoro.sources))
            origini = esistente.setdefault("provenienze", [])
            if provenienza not in origini:
                origini.append(provenienza)
            if cambiati:
                progetto_corrente.setdefault("versioni_record", {}).setdefault(
                    esistente["id"], []
                ).append({
                    "quando": _adesso(), "ricerca": id_ricerca,
                    "campi": cambiati, "prima": prima,
                })
                quanti["modificati"] += 1
                if not prima.get("ritirato") and dati.get("ritirato"):
                    quanti["ritirati"] += 1
        voce_aggiornata = history.voce(id_ricerca) or {}
        progetto_corrente.setdefault("ricerche", []).append({
            "id": id_ricerca,
            "topic": voce_aggiornata.get("topic", "aggiornamento"),
            "quando": voce_aggiornata.get("quando", _adesso()),
            "fonti": [f.get("etichetta", "") for f in voce_aggiornata.get("fonti", [])],
            "interrogazioni": [
                {
                    "fonte": f.get("etichetta", ""), "query": f.get("query", ""),
                    "oql": f.get("oql", ""), "trovati": f.get("trovati", 0),
                }
                for f in voce_aggiornata.get("fonti", [])
            ],
            "blocchi": voce_aggiornata.get("blocchi", []),
            "mesh": voce_aggiornata.get("mesh", []),
            "filtri": voce_aggiornata.get("filtri", {}),
            "aggiornamento": True,
        })
        dato = {
            "quando": _adesso(), **quanti,
            "nota": f"Esecuzione {id_ricerca}",
        }
        progetto_corrente.setdefault("aggiornamenti", []).append(dato)
        _evento(
            progetto_corrente,
            "aggiornamento automatico",
            f"{quanti['nuovi']} nuovi · {quanti['modificati']} modificati",
        )
        return quanti

    return _modifica(id_progetto, applica) or {"nuovi": 0, "modificati": 0, "ritirati": 0}


def _campi_work(dati: dict) -> dict:
    ammessi = set(Work.__dataclass_fields__)
    return {chiave: valore for chiave, valore in dati.items() if chiave in ammessi}


def lavori(progetto_corrente: dict) -> list[dict]:
    """Record del workspace pronti per il template, senza mutare il JSON."""

    risultati = []
    for item in progetto_corrente.get("record", []):
        risultati.append({**item, "work": Work(**_campi_work(item.get("record", {})))})
    return risultati


def item(progetto_corrente: dict, id_item: str) -> dict | None:
    return next((r for r in progetto_corrente.get("record", []) if r.get("id") == id_item), None)


def decidi(
    id_progetto: str,
    id_item: str,
    fase: str,
    revisore: str,
    stato: str,
    motivo: str = "",
) -> dict:
    if fase not in FASI_SCREENING or stato not in STATI or not revisore.strip():
        return {}

    def applica(progetto_corrente: dict):
        if item(progetto_corrente, id_item) is None:
            return {}
        decisioni = progetto_corrente.setdefault("decisioni", {})
        per_item = decisioni.setdefault(id_item, {}).setdefault(fase, {})
        per_item[revisore.strip()] = {
            "stato": stato,
            "motivo": motivo.strip(),
            "quando": _adesso(),
        }
        progetto_corrente.setdefault("consenso", {}).setdefault(id_item, {}).pop(fase, None)
        _evento(progetto_corrente, "screening", f"{fase} · {revisore} · {stato}")
        return per_item

    return _modifica(id_progetto, applica) or {}


def risolvi(id_progetto: str, id_item: str, fase: str, stato: str, motivo: str = "") -> dict:
    if fase not in FASI_SCREENING or stato not in STATI:
        return {}

    def applica(progetto_corrente: dict):
        if item(progetto_corrente, id_item) is None:
            return {}
        dato = {"stato": stato, "motivo": motivo.strip(), "quando": _adesso()}
        progetto_corrente.setdefault("consenso", {}).setdefault(id_item, {})[fase] = dato
        _evento(progetto_corrente, "conflitto risolto", f"{fase} · {stato}")
        return dato

    return _modifica(id_progetto, applica) or {}


def salva_testo_completo(id_progetto: str, id_item: str, stato: str, nota: str = "") -> dict:
    if stato not in STATI_TESTO_COMPLETO:
        return {}

    def applica(progetto_corrente: dict):
        if item(progetto_corrente, id_item) is None:
            return {}
        dato = {"stato": stato, "nota": nota.strip(), "quando": _adesso()}
        progetto_corrente.setdefault("testi_completi", {})[id_item] = dato
        _evento(progetto_corrente, "testo completo", f"{id_item} · {stato}")
        return dato

    return _modifica(id_progetto, applica) or {}


def decisioni_item(progetto_corrente: dict, id_item: str, fase: str) -> dict:
    return progetto_corrente.get("decisioni", {}).get(id_item, {}).get(fase, {})


def stato_finale(progetto_corrente: dict, id_item: str, fase: str) -> str:
    consenso = progetto_corrente.get("consenso", {}).get(id_item, {}).get(fase, {})
    if consenso.get("stato") in STATI:
        return consenso["stato"]
    decisioni = decisioni_item(progetto_corrente, id_item, fase)
    revisori = progetto_corrente.get("revisori", [])
    if any(revisore not in decisioni for revisore in revisori):
        return ""
    stati = {
        d.get("stato") for d in decisioni.values()
        if d.get("stato") in STATI
    }
    return next(iter(stati)) if len(stati) == 1 else ""


def conflitti(id_progetto: str, fase: str) -> list[str]:
    progetto_corrente = progetto(id_progetto) or {}
    trovati = []
    for record in progetto_corrente.get("record", []):
        id_item = record.get("id", "")
        if progetto_corrente.get("consenso", {}).get(id_item, {}).get(fase):
            continue
        decisioni = decisioni_item(progetto_corrente, id_item, fase)
        if any(revisore not in decisioni for revisore in progetto_corrente.get("revisori", [])):
            continue
        stati = {
            d.get("stato") for d in decisioni.values()
            if d.get("stato") in STATI
        }
        if len(stati) > 1:
            trovati.append(id_item)
    return trovati


def conteggi_screening(progetto_corrente: dict, fase: str) -> dict[str, int]:
    conta = {stato: 0 for stato in STATI}
    conta.update({"conflitti": 0, "da_valutare": 0})
    conflitto_ids = set()
    for record in progetto_corrente.get("record", []):
        id_item = record.get("id", "")
        decisioni = decisioni_item(progetto_corrente, id_item, fase)
        stati = {d.get("stato") for d in decisioni.values() if d.get("stato") in STATI}
        tutti = all(
            revisore in decisioni for revisore in progetto_corrente.get("revisori", [])
        )
        if tutti and len(stati) > 1 and not progetto_corrente.get("consenso", {}).get(id_item, {}).get(fase):
            conflitto_ids.add(id_item)
            continue
        stato = stato_finale(progetto_corrente, id_item, fase)
        if stato:
            conta[stato] += 1
        else:
            conta["da_valutare"] += 1
    conta["conflitti"] = len(conflitto_ids)
    return conta


def collega_report(id_progetto: str, id_report: str, id_studio: str) -> dict:
    def applica(progetto_corrente: dict):
        if item(progetto_corrente, id_report) is None or item(progetto_corrente, id_studio) is None:
            return {}
        progetto_corrente.setdefault("gruppi_studio", {})[id_report] = id_studio
        _evento(progetto_corrente, "report collegato", f"{id_report} → {id_studio}")
        return progetto_corrente["gruppi_studio"]

    return _modifica(id_progetto, applica) or {}


def salva_estrazione(id_progetto: str, id_item: str, revisore: str, dati: dict) -> dict:
    puliti = {campo: str(dati.get(campo, "")).strip() for campo in CAMPI_ESTRAZIONE}

    def applica(progetto_corrente: dict):
        if item(progetto_corrente, id_item) is None or not revisore.strip():
            return {}
        progetto_corrente.setdefault("estrazioni", {}).setdefault(id_item, {})[
            revisore.strip()
        ] = {**puliti, "quando": _adesso()}
        _evento(progetto_corrente, "estrazione salvata", f"{revisore} · {id_item}")
        return puliti

    return _modifica(id_progetto, applica) or {}


def conflitto_estrazione(progetto_corrente: dict, id_item: str) -> bool:
    estrazioni = progetto_corrente.get("estrazioni", {}).get(id_item, {})
    revisori = progetto_corrente.get("revisori", [])
    if len(revisori) < 2 or any(revisore not in estrazioni for revisore in revisori):
        return False
    if id_item in progetto_corrente.get("consenso_estrazioni", {}):
        return False
    firme = {
        tuple(str(estrazioni[revisore].get(campo, "")).strip() for campo in CAMPI_ESTRAZIONE)
        for revisore in revisori
    }
    return len(firme) > 1


def salva_consenso_estrazione(id_progetto: str, id_item: str, dati: dict) -> dict:
    puliti = {campo: str(dati.get(campo, "")).strip() for campo in CAMPI_ESTRAZIONE}

    def applica(progetto_corrente: dict):
        if item(progetto_corrente, id_item) is None:
            return {}
        progetto_corrente.setdefault("consenso_estrazioni", {})[id_item] = {
            **puliti, "quando": _adesso()
        }
        _evento(progetto_corrente, "consenso estrazione", id_item)
        return puliti

    return _modifica(id_progetto, applica) or {}


def salva_bias(id_progetto: str, id_item: str, dati: dict) -> dict:
    puliti = {campo: str(dati.get(campo, "")).strip() for campo in CAMPI_BIAS}

    def applica(progetto_corrente: dict):
        if item(progetto_corrente, id_item) is None:
            return {}
        progetto_corrente.setdefault("bias", {})[id_item] = {**puliti, "quando": _adesso()}
        _evento(progetto_corrente, "qualità valutata", id_item)
        return puliti

    return _modifica(id_progetto, applica) or {}


def salva_wiki(id_progetto: str, dati: dict) -> dict:
    """Sostituisce soltanto l'artefatto ricostruibile della wiki."""

    def applica(progetto_corrente: dict):
        progetto_corrente["wiki"] = dati
        _evento(
            progetto_corrente,
            "wiki aggiornata",
            f"{len(dati.get('nodi', []))} nodi · {len(dati.get('archi', []))} relazioni",
        )
        return dati

    return _modifica(id_progetto, applica) or {}


def salva_evidenza(id_progetto: str, dati: dict) -> dict:
    puliti = {campo: str(dati.get(campo, "")).strip() for campo in CAMPI_EVIDENZA}
    puliti["id"] = secrets.token_urlsafe(6)
    puliti["quando"] = _adesso()

    def applica(progetto_corrente: dict):
        progetto_corrente.setdefault("evidenze", []).append(puliti)
        _evento(progetto_corrente, "evidenza aggiunta", puliti.get("outcome", ""))
        return puliti

    return _modifica(id_progetto, applica) or {}


def elimina_evidenza(id_progetto: str, id_evidenza: str) -> bool:
    def applica(progetto_corrente: dict):
        prima = len(progetto_corrente.get("evidenze", []))
        progetto_corrente["evidenze"] = [
            e for e in progetto_corrente.get("evidenze", []) if e.get("id") != id_evidenza
        ]
        cambiato = len(progetto_corrente["evidenze"]) != prima
        if cambiato:
            _evento(progetto_corrente, "evidenza rimossa", id_evidenza)
        return cambiato

    return bool(_modifica(id_progetto, applica))


_STOP = {
    "the", "and", "for", "with", "from", "this", "that", "study", "review",
    "una", "uno", "con", "per", "della", "delle", "degli", "studio", "ricerca",
}


def _token(testo: str) -> list[str]:
    pulito = unicodedata.normalize("NFKD", testo.casefold())
    pulito = "".join(c for c in pulito if not unicodedata.combining(c))
    return [p for p in re.findall(r"[a-z0-9]{3,}", pulito) if p not in _STOP]


def priorita_assistita(progetto_corrente: dict, fase: str = "abstract") -> list[dict]:
    """Ordina i non valutati con un modello trasparente a frequenze di termini.

    Non esclude mai un record e restituisce i termini che spiegano il punteggio.
    """

    positivi, negativi = Counter(), Counter()
    for record in progetto_corrente.get("record", []):
        id_item = record.get("id", "")
        stato = stato_finale(progetto_corrente, id_item, fase)
        lavoro = Work(**_campi_work(record.get("record", {})))
        termini = set(_token(f"{lavoro.title} {lavoro.abstract or ''}"))
        if stato == "incluso":
            positivi.update(termini)
        elif stato == "escluso":
            negativi.update(termini)

    ordinati = []
    for record in progetto_corrente.get("record", []):
        id_item = record.get("id", "")
        if stato_finale(progetto_corrente, id_item, fase):
            continue
        lavoro = Work(**_campi_work(record.get("record", {})))
        termini = set(_token(f"{lavoro.title} {lavoro.abstract or ''}"))
        contributi = {termine: positivi[termine] - negativi[termine] for termine in termini}
        utili = sorted((t for t, valore in contributi.items() if valore > 0), key=lambda t: (-contributi[t], t))
        punteggio = sum(max(0, valore) for valore in contributi.values()) / max(1, len(termini))
        ordinati.append({
            **record,
            "work": lavoro,
            "punteggio": round(float(punteggio), 4),
            "termini": utili[:5],
        })
    return sorted(ordinati, key=lambda r: (-r["punteggio"], r["work"].title.casefold()))


def registra_aggiornamento(
    id_progetto: str,
    nuovi: int,
    modificati: int = 0,
    ritirati: int = 0,
    nota: str = "",
) -> dict:
    dato = {
        "quando": _adesso(), "nuovi": int(nuovi), "modificati": int(modificati),
        "ritirati": int(ritirati), "nota": nota.strip(),
    }

    def applica(progetto_corrente: dict):
        progetto_corrente.setdefault("aggiornamenti", []).append(dato)
        _evento(progetto_corrente, "aggiornamento controllato", f"{nuovi} nuovi")
        return dato

    return _modifica(id_progetto, applica) or {}


def aggiornamento_dovuto(progetto_corrente: dict, oggi: date | None = None) -> bool:
    frequenza = progetto_corrente.get("protocollo", {}).get("frequenza_aggiornamento", "")
    giorni = {"settimanale": 7, "mensile": 30, "trimestrale": 90}.get(frequenza)
    if not giorni:
        return False
    ultimo = (progetto_corrente.get("aggiornamenti") or [{}])[-1].get(
        "quando", progetto_corrente.get("creato", "")
    )
    try:
        data_ultima = datetime.fromisoformat(ultimo).date()
    except (TypeError, ValueError):
        return True
    return (oggi or date.today()) >= data_ultima + timedelta(days=giorni)


def checklist_prisma_s(progetto_corrente: dict) -> list[dict]:
    protocollo = progetto_corrente.get("protocollo", {})
    ricerche = progetto_corrente.get("ricerche", [])
    emendamenti = progetto_corrente.get("emendamenti", [])
    controlli = [
        ("sources", "Fonti e piattaforme dichiarate", bool(protocollo.get("fonti_previste") or ricerche)),
        ("strategies", "Strategie complete conservate", bool(ricerche) and all(r.get("interrogazioni") for r in ricerche)),
        ("dates", "Date delle ricerche conservate", bool(ricerche) and all(r.get("quando") for r in ricerche)),
        ("limits", "Limiti motivati nei criteri", bool(protocollo.get("criteri_inclusione"))),
        ("deduplication", "Deduplica documentata", bool(progetto_corrente.get("record"))),
        ("updates", "Aggiornamenti descritti", bool(protocollo.get("frequenza_aggiornamento"))),
        ("peer_review", "Peer review della strategia registrata", bool(protocollo.get("peer_review_strategia"))),
        ("amendments", "Modifiche del protocollo tracciate", bool(emendamenti) or bool(protocollo)),
    ]
    return [
        {"chiave": chiave, "etichetta": etichetta, "completo": completo}
        for chiave, etichetta, completo in controlli
    ]


def controlla_sentinelle(progetto_corrente: dict) -> list[dict]:
    """Verifica che titoli o DOI noti a priori compaiano davvero nel corpus."""

    testo = progetto_corrente.get("protocollo", {}).get("articoli_sentinella", "")
    attese = [riga.strip() for riga in re.split(r"[\n;]+", testo) if riga.strip()]
    record = [Work(**_campi_work(item.get("record", {}))) for item in progetto_corrente.get("record", [])]
    esiti = []
    for attesa in attese:
        chiave = " ".join(_token(attesa))
        trovata = any(
            attesa.casefold().strip().removeprefix("https://doi.org/")
            == (lavoro.doi or "").casefold().strip().removeprefix("https://doi.org/")
            or (chiave and chiave in " ".join(_token(lavoro.title)))
            for lavoro in record
        )
        esiti.append({"valore": attesa, "trovata": trovata})
    return esiti


def riepilogo(progetto_corrente: dict) -> dict:
    record = progetto_corrente.get("record", [])
    return {
        "record": len(record),
        "ricerche": len(progetto_corrente.get("ricerche", [])),
        "protocollo_mancanti": len(campi_protocollo_mancanti(progetto_corrente)),
        "abstract": conteggi_screening(progetto_corrente, "abstract"),
        "fulltext": conteggi_screening(progetto_corrente, "fulltext"),
        "estratti": len(progetto_corrente.get("estrazioni", {})),
        "bias": len(progetto_corrente.get("bias", {})),
        "evidenze": len(progetto_corrente.get("evidenze", [])),
        "ritirati": sum(1 for r in record if r.get("record", {}).get("ritirato")),
    }


def esporta_markdown(progetto_corrente: dict) -> str:
    protocollo = progetto_corrente.get("protocollo", {})
    righe = [
        f"# {progetto_corrente.get('titolo', 'Review')}", "",
        f"Tipo: {progetto_corrente.get('tipo', '')}",
        f"Revisori: {', '.join(progetto_corrente.get('revisori', []))}", "",
        "## Protocollo", "",
    ]
    for campo in CAMPI_PROTOCOLLO:
        if protocollo.get(campo):
            righe.append(f"- {campo.replace('_', ' ')}: {protocollo[campo]}")
    righe += ["", "## Ricerche", ""]
    for ricerca in progetto_corrente.get("ricerche", []):
        righe.append(
            f"- {ricerca.get('quando', '')} — {ricerca.get('topic', '')} "
            f"({', '.join(ricerca.get('fonti', []))})"
        )
        for interrogazione in ricerca.get("interrogazioni", []):
            righe.append(
                f"  - {interrogazione.get('fonte', '')}: "
                f"`{interrogazione.get('query', '')}` — {interrogazione.get('trovati', 0)} record"
            )
            if interrogazione.get("oql"):
                righe.append(f"    - OQL: `{interrogazione['oql']}`")
    riepilogo_corrente = riepilogo(progetto_corrente)
    righe += [
        "", "## Selezione", "",
        f"- record nel corpus: {riepilogo_corrente['record']}",
        f"- inclusi a titolo/abstract: {riepilogo_corrente['abstract']['incluso']}",
        f"- inclusi a testo completo: {riepilogo_corrente['fulltext']['incluso']}",
        f"- conflitti aperti: {riepilogo_corrente['abstract']['conflitti'] + riepilogo_corrente['fulltext']['conflitti']}",
    ]
    for fase, etichetta in (("abstract", "Titolo/abstract"), ("fulltext", "Testo completo")):
        conta = riepilogo_corrente[fase]
        righe.append(
            f"- {etichetta}: inclusi {conta['incluso']}, forse {conta['forse']}, "
            f"esclusi {conta['escluso']}, da valutare {conta['da_valutare']}"
        )
    esclusioni = []
    for record in progetto_corrente.get("record", []):
        id_item = record.get("id", "")
        titolo = record.get("record", {}).get("title", "")
        for fase in FASI_SCREENING:
            if stato_finale(progetto_corrente, id_item, fase) != "escluso":
                continue
            consenso = progetto_corrente.get("consenso", {}).get(id_item, {}).get(fase, {})
            motivi = [
                d.get("motivo", "") for d in decisioni_item(progetto_corrente, id_item, fase).values()
                if d.get("motivo")
            ]
            motivo = consenso.get("motivo") or "; ".join(dict.fromkeys(motivi))
            esclusioni.append(f"- {titolo} — {fase}: {motivo or 'motivo non registrato'}")
    if esclusioni:
        righe += ["", "### Studi esclusi e motivi", "", *esclusioni]

    testi = progetto_corrente.get("testi_completi", {})
    if testi:
        righe += ["", "### Reperimento dei testi completi", ""]
        for record in progetto_corrente.get("record", []):
            dato = testi.get(record.get("id", ""))
            if dato:
                righe.append(
                    f"- {record.get('record', {}).get('title', '')}: {dato.get('stato', '')}"
                    + (f" — {dato.get('nota')}" if dato.get("nota") else "")
                )

    gruppi = progetto_corrente.get("gruppi_studio", {})
    if gruppi:
        titoli = {r.get("id"): r.get("record", {}).get("title", "") for r in progetto_corrente.get("record", [])}
        righe += ["", "## Studi e report collegati", ""]
        righe += [f"- {titoli.get(report, report)} → {titoli.get(studio, studio)}" for report, studio in gruppi.items()]

    estrazioni = progetto_corrente.get("consenso_estrazioni", {}) or {
        id_item: next(iter(per_revisore.values()))
        for id_item, per_revisore in progetto_corrente.get("estrazioni", {}).items()
        if per_revisore
    }
    if estrazioni:
        titoli = {r.get("id"): r.get("record", {}).get("title", "") for r in progetto_corrente.get("record", [])}
        righe += ["", "## Estrazione dei dati", ""]
        for id_item, dati in estrazioni.items():
            righe.append(f"### {titoli.get(id_item, id_item)}")
            righe += [f"- {campo}: {dati.get(campo, '')}" for campo in CAMPI_ESTRAZIONE if dati.get(campo)]

    if progetto_corrente.get("bias"):
        titoli = {r.get("id"): r.get("record", {}).get("title", "") for r in progetto_corrente.get("record", [])}
        righe += ["", "## Valutazione critica", ""]
        for id_item, dati in progetto_corrente["bias"].items():
            righe.append(
                f"- **{titoli.get(id_item, id_item)}** — {dati.get('strumento', '')}: "
                f"{dati.get('giudizio', '')}. {dati.get('motivazione', '')}"
            )

    righe += ["", "## PRISMA-S", ""]
    righe += [
        f"- [{'x' if voce['completo'] else ' '}] {voce['etichetta']}"
        for voce in checklist_prisma_s(progetto_corrente)
    ]
    if progetto_corrente.get("evidenze"):
        righe += ["", "## Summary of findings", ""]
        for evidenza in progetto_corrente["evidenze"]:
            righe.append(
                f"- **{evidenza.get('outcome', '')}** — {evidenza.get('effetto', '')}; "
                f"certezza {evidenza.get('certezza', '')}. {evidenza.get('motivazione', '')}"
            )
    wiki_corrente = progetto_corrente.get("wiki", {})
    if wiki_corrente:
        concetti = [
            pagina for pagina in wiki_corrente.get("pagine", [])
            if pagina.get("tipo") == "concetto"
        ]
        righe += [
            "", "## Wiki e grafo della letteratura", "",
            f"- generata: {wiki_corrente.get('generata', '')}",
            f"- ambito semantico: {wiki_corrente.get('ambito', '')}",
            f"- nodi: {len(wiki_corrente.get('nodi', []))}",
            f"- relazioni: {len(wiki_corrente.get('archi', []))}",
            f"- modello: {wiki_corrente.get('modello') or 'solo metadati'}",
        ]
        for pagina in concetti:
            righe.append(
                f"- **{pagina.get('titolo', '')}** — {pagina.get('riassunto', '')}"
            )
    if progetto_corrente.get("aggiornamenti"):
        righe += ["", "## Aggiornamenti", ""]
        for voce in progetto_corrente["aggiornamenti"]:
            righe.append(
                f"- {voce.get('quando', '')}: {voce.get('nuovi', 0)} nuovi, "
                f"{voce.get('modificati', 0)} modificati, {voce.get('ritirati', 0)} ritirati"
                + (f" — {voce.get('nota')}" if voce.get("nota") else "")
            )
    if progetto_corrente.get("emendamenti"):
        righe += ["", "## Emendamenti del protocollo", ""]
        for voce in progetto_corrente["emendamenti"]:
            righe.append(
                f"- {voce.get('quando', '')}: {voce.get('motivo', '')} "
                f"({', '.join(voce.get('campi', {}))})"
            )
    return "\n".join(righe).rstrip() + "\n"
