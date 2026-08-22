"""Filtri di lettura per il corpus di una review.

Sintassi delle query testuali: termini separati da AND, OR e NOT, senza
distinguere maiuscole. NOT nega il termine che segue; AND lega più forte di
OR. Un termine è una sottostringa cercata nel campo senza distinzione di
maiuscole. Query vuota: passa tutto.
"""

from __future__ import annotations

import re

_SEP_AND = re.compile(r"\s+AND\s+", re.IGNORECASE)
_SEP_OR = re.compile(r"\s+OR\s+", re.IGNORECASE)


def corrisponde(query: str, testo: str | None) -> bool:
    """True se il testo soddisfa la query booleana (o se la query è vuota)."""

    query = (query or "").strip()
    if not query:
        return True
    testo = (testo or "").lower()
    return any(_valuta_and(parte, testo) for parte in _SEP_OR.split(query))


def _valuta_and(parte: str, testo: str) -> bool:
    for pezzo in _SEP_AND.split(parte):
        for termine, negato in _termini(pezzo):
            if (termine.lower() in testo) == negato:
                return False
    return True


def _termini(pezzo: str) -> list[tuple[str, bool]]:
    """Scompone un pezzo in termini, ognuno con il proprio NOT.

    NOT nega il singolo token che segue; i token senza operatori si uniscono
    in un unico termine, così «AI literacy» cerca la frase intera.
    """

    termini, corrente, negato = [], [], False

    def chiudi():
        nonlocal corrente, negato
        if corrente:
            termini.append((" ".join(corrente), negato))
            corrente, negato = [], False

    for token in pezzo.split():
        if token.upper() == "NOT":
            chiudi()
            negato = True
            continue
        corrente.append(token)
        if negato:
            chiudi()
            negato = False
    chiudi()
    return termini


def _intero(valore) -> int | None:
    if valore is None:
        return None
    testo = str(valore).strip()
    if not testo:
        return None
    try:
        return int(testo)
    except ValueError:
        return None


def filtra_record(voce: dict, filtri: dict) -> bool:
    """True se il record passa tutti i filtri attivi.

    I filtri vivono nel protocollo della review: ``anno_da``/``anno_a`` sono
    estremi inclusivi, ``keywords`` cerca in titolo e abstract, ``titolo`` e
    ``abstract`` nei rispettivi campi. Valori vuoti o assenti: filtro spento.
    """

    work = voce.get("work")
    if not work:
        return True
    anno_da = _intero(filtri.get("filtro_anno_da"))
    anno_a = _intero(filtri.get("filtro_anno_a"))
    if anno_da is not None or anno_a is not None:
        if work.year is None:
            return False
        if anno_da is not None and work.year < anno_da:
            return False
        if anno_a is not None and work.year > anno_a:
            return False
    titolo, abstract = work.title or "", work.abstract or ""
    if not corrisponde(filtri.get("filtro_keywords"), f"{titolo}\n{abstract}"):
        return False
    if not corrisponde(filtri.get("filtro_titolo"), titolo):
        return False
    if not corrisponde(filtri.get("filtro_abstract"), abstract):
        return False
    return True
