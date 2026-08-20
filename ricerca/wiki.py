"""Wiki e grafo della letteratura, ricostruibili dal corpus di una review."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime

from . import revisioni


SCHEMA = 1


def _adesso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _slug(testo: str) -> str:
    base = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", base.casefold()).strip("-")[:80] or "voce"


def firma_corpus(progetto: dict) -> str:
    dati = [
        {
            "id": voce.get("id", ""),
            "title": voce.get("record", {}).get("title", ""),
            "abstract": voce.get("record", {}).get("abstract", ""),
            "authors": voce.get("record", {}).get("authors", []),
            "venue": voce.get("record", {}).get("venue", ""),
            "year": voce.get("record", {}).get("year"),
        }
        for voce in progetto.get("record", [])
    ]
    grezzi = json.dumps(dati, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(grezzi).hexdigest()[:20]


def obsoleta(progetto: dict) -> bool:
    wiki = progetto.get("wiki", {})
    return bool(wiki) and wiki.get("firma_corpus") != firma_corpus(progetto)


def documenti_semantici(progetto: dict) -> tuple[list[dict], str]:
    """Usa gli inclusi quando esistono, altrimenti il corpus ancora da vagliare."""

    tutti = progetto.get("record", [])
    inclusi_fulltext = [
        voce for voce in tutti
        if revisioni.stato_finale(progetto, voce.get("id", ""), "fulltext") == "incluso"
    ]
    inclusi_abstract = [
        voce for voce in tutti
        if revisioni.stato_finale(progetto, voce.get("id", ""), "abstract") == "incluso"
    ]
    if inclusi_fulltext:
        return inclusi_fulltext, "fulltext_inclusi"
    if inclusi_abstract:
        return inclusi_abstract, "abstract_inclusi"
    return tutti, "corpus"


def crea_base(progetto: dict) -> dict:
    """Crea pagine-fonte e relazioni bibliografiche senza inventare contenuto."""

    nodi: dict[str, dict] = {}
    archi: list[dict] = []
    pagine: list[dict] = []
    archi_visti: set[tuple[str, str, str]] = set()

    def nodo(id_nodo: str, tipo: str, etichetta: str, **extra) -> None:
        if id_nodo not in nodi:
            nodi[id_nodo] = {"id": id_nodo, "tipo": tipo, "etichetta": etichetta, **extra}

    def arco(origine: str, destinazione: str, tipo: str, fonte: str) -> None:
        firma = (origine, destinazione, tipo)
        if firma in archi_visti:
            return
        archi_visti.add(firma)
        archi.append({
            "origine": origine, "destinazione": destinazione, "tipo": tipo,
            "fonti": [fonte], "evidenza": "metadati",
        })

    for voce in progetto.get("record", []):
        id_fonte = voce.get("id", "")
        if not id_fonte:
            continue
        dati = voce.get("record", {})
        id_nodo = f"fonte:{id_fonte}"
        titolo = str(dati.get("title", "")).strip() or "Senza titolo"
        stato_fulltext = revisioni.stato_finale(progetto, id_fonte, "fulltext")
        stato_abstract = revisioni.stato_finale(progetto, id_fonte, "abstract")
        nodo(
            id_nodo, "fonte", titolo, id_fonte=id_fonte,
            anno=dati.get("year"), stato=stato_fulltext or stato_abstract or "da_valutare",
        )
        pagine.append({
            "id": id_nodo, "tipo": "fonte", "titolo": titolo,
            "riassunto": str(dati.get("abstract") or "").strip(),
            "autori": list(dati.get("authors") or []), "anno": dati.get("year"),
            "sede": str(dati.get("venue") or ""), "doi": str(dati.get("doi") or ""),
            "url": str(dati.get("url") or ""), "id_fonte": id_fonte,
            "stato": stato_fulltext or stato_abstract or "da_valutare",
        })
        for autore in dati.get("authors") or []:
            id_autore = f"autore:{_slug(str(autore))}"
            nodo(id_autore, "autore", str(autore))
            arco(id_nodo, id_autore, "scritto_da", id_fonte)
        sede = str(dati.get("venue") or "").strip()
        if sede:
            id_sede = f"sede:{_slug(sede)}"
            nodo(id_sede, "sede", sede)
            arco(id_nodo, id_sede, "pubblicato_in", id_fonte)

    semantici, ambito = documenti_semantici(progetto)
    return {
        "schema": SCHEMA,
        "generata": _adesso(),
        "firma_corpus": firma_corpus(progetto),
        "ambito": ambito,
        "record_semantici": len(semantici),
        "llm_usato": False,
        "modello": "",
        "errore_llm": "",
        "nodi": list(nodi.values()),
        "archi": archi,
        "pagine": pagine,
    }


def documenti_per_llm(progetto: dict) -> list[dict]:
    documenti, _ = documenti_semantici(progetto)
    return [
        {
            "id": voce.get("id", ""),
            "title": str(voce.get("record", {}).get("title", ""))[:400],
            "authors": list(voce.get("record", {}).get("authors", []))[:20],
            "year": voce.get("record", {}).get("year"),
            "venue": str(voce.get("record", {}).get("venue", ""))[:300],
            "abstract": str(voce.get("record", {}).get("abstract", ""))[:3200],
        }
        for voce in documenti
        if voce.get("id") and voce.get("record", {}).get("abstract")
    ]


def _citazione_valida(citazione: str, fonti: list[str], testi: dict[str, str]) -> str:
    pulita = " ".join(str(citazione).split())[:240]
    if not pulita:
        return ""
    ago = pulita.casefold()
    return pulita if any(ago in testi.get(id_fonte, "").casefold() for id_fonte in fonti) else ""


def arricchisci(base: dict, risultati: list[dict], documenti: list[dict], modello: str) -> dict:
    """Unisce risposte LLM validate: soltanto fonti e citazioni realmente presenti."""

    ammessi = {documento["id"] for documento in documenti}
    testi = {documento["id"]: " ".join(str(documento.get("abstract", "")).split()) for documento in documenti}
    nodi = {nodo["id"]: nodo for nodo in base.get("nodi", [])}
    archi = list(base.get("archi", []))
    pagine = list(base.get("pagine", []))
    pagine_concetto: dict[str, dict] = {}
    mappe_locali: list[dict[str, str]] = []

    for risultato in risultati:
        id_locali: dict[str, str] = {}
        for concetto in risultato.get("concetti", []):
            etichetta = " ".join(str(concetto.get("etichetta", "")).split())[:120]
            if not etichetta:
                continue
            id_globale = f"concetto:{_slug(etichetta)}"
            fonti = sorted({str(f) for f in concetto.get("fonti", []) if str(f) in ammessi})
            if not fonti:
                continue
            id_locali[str(concetto.get("id", ""))] = id_globale
            nodo = nodi.setdefault(id_globale, {
                "id": id_globale, "tipo": "concetto", "etichetta": etichetta,
            })
            pagina = pagine_concetto.setdefault(id_globale, {
                "id": id_globale, "tipo": "concetto", "titolo": nodo["etichetta"],
                "riassunto": "", "fonti": [], "evidenze": [],
            })
            riassunto = " ".join(str(concetto.get("riassunto", "")).split())[:1200]
            if len(riassunto) > len(pagina["riassunto"]):
                pagina["riassunto"] = riassunto
            pagina["fonti"] = sorted(set(pagina["fonti"]) | set(fonti))
            citazione = _citazione_valida(concetto.get("evidenza", ""), fonti, testi)
            if citazione and not any(e.get("testo") == citazione for e in pagina["evidenze"]):
                pagina["evidenze"].append({"testo": citazione, "fonti": fonti})
            for id_fonte in fonti:
                archi.append({
                    "origine": f"fonte:{id_fonte}", "destinazione": id_globale,
                    "tipo": "tratta", "fonti": [id_fonte], "evidenza": citazione,
                })
        mappe_locali.append(id_locali)

    for risultato, id_locali in zip(risultati, mappe_locali):
        for relazione in risultato.get("relazioni", []):
            origine = id_locali.get(str(relazione.get("origine", "")))
            destinazione = id_locali.get(str(relazione.get("destinazione", "")))
            fonti = sorted({str(f) for f in relazione.get("fonti", []) if str(f) in ammessi})
            if not origine or not destinazione or origine == destinazione or not fonti:
                continue
            archi.append({
                "origine": origine, "destinazione": destinazione,
                "tipo": str(relazione.get("tipo", "associato_a"))[:40],
                "fonti": fonti,
                "evidenza": _citazione_valida(relazione.get("evidenza", ""), fonti, testi),
            })

    base.update({
        "llm_usato": bool(pagine_concetto), "modello": modello if pagine_concetto else "",
        "nodi": list(nodi.values()), "archi": _archi_unici(archi),
        "pagine": [*pagine_concetto.values(), *pagine],
    })
    return base


def _archi_unici(archi: list[dict]) -> list[dict]:
    unici: dict[tuple[str, str, str], dict] = {}
    for arco in archi:
        chiave = (arco.get("origine", ""), arco.get("destinazione", ""), arco.get("tipo", ""))
        if not all(chiave):
            continue
        if chiave not in unici:
            unici[chiave] = arco
            continue
        esistente = unici[chiave]
        esistente["fonti"] = sorted(set(esistente.get("fonti", [])) | set(arco.get("fonti", [])))
        if not esistente.get("evidenza") and arco.get("evidenza"):
            esistente["evidenza"] = arco["evidenza"]
    return list(unici.values())


def statistiche(wiki: dict) -> dict:
    tipi = {}
    for nodo in wiki.get("nodi", []):
        tipi[nodo.get("tipo", "")] = tipi.get(nodo.get("tipo", ""), 0) + 1
    return {
        "pagine": len(wiki.get("pagine", [])),
        "nodi": len(wiki.get("nodi", [])),
        "archi": len(wiki.get("archi", [])),
        "concetti": tipi.get("concetto", 0),
        "fonti": tipi.get("fonte", 0),
    }
