"""Testo dei PDF scaricati, per cercarci dentro.

Il testo viene estratto una volta sola, subito dopo lo scaricamento, e
salvato accanto al PDF: la ricerca è poi una scansione di file di testo.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import config as config_module

CONTORNO = 120  # caratteri mostrati attorno alla parola trovata


def cartella() -> Path:
    percorso = config_module.CONFIG_DIR / "pdf"
    percorso.mkdir(parents=True, exist_ok=True)
    return percorso


def percorso_testo(pdf: Path) -> Path:
    return pdf.with_suffix(".txt")


def estrai(pdf: Path) -> Path | None:
    """Scrive il testo del PDF accanto al file. Senza pypdf non fa nulla."""

    try:
        from pypdf import PdfReader
    except ImportError:
        return None

    try:
        lettore = PdfReader(str(pdf))
        pagine = [pagina.extract_text() or "" for pagina in lettore.pages]
    except Exception:
        return None

    testo = "\n".join(pagine).strip()
    if not testo:
        return None
    destinazione = percorso_testo(pdf)
    destinazione.write_text(testo, encoding="utf-8")
    return destinazione


def documenti() -> list[Path]:
    return sorted(cartella().glob("*.txt"))


def cerca(query: str, massimo: int = 50) -> list[dict]:
    """Cerca una parola o una frase nei PDF già scaricati."""

    query = query.strip()
    if not query:
        return []
    modello = re.compile(re.escape(query), re.IGNORECASE)

    trovati = []
    for testo in documenti():
        try:
            contenuto = testo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        occorrenze = list(modello.finditer(contenuto))
        if not occorrenze:
            continue
        prima = occorrenze[0]
        inizio = max(prima.start() - CONTORNO, 0)
        fine = min(prima.end() + CONTORNO, len(contenuto))
        trovati.append(
            {
                "file": testo.with_suffix(".pdf").name,
                "occorrenze": len(occorrenze),
                "estratto": " ".join(contenuto[inizio:fine].split()),
            }
        )
        if len(trovati) >= massimo:
            break
    return sorted(trovati, key=lambda t: -t["occorrenze"])


def percorso_pdf(nome: str) -> Path | None:
    """Il PDF di un risultato, per nome di file.

    Il nome arriva dall'indirizzo: si accetta soltanto un file che stia
    davvero nella cartella dei PDF, senza passare per «..» o per un
    collegamento che porti altrove.
    """

    if not nome.endswith(".pdf") or "/" in nome or "\\" in nome:
        return None
    cartella_pdf = cartella().resolve()
    candidato = (cartella_pdf / nome).resolve()
    if candidato.parent != cartella_pdf or not candidato.is_file():
        return None
    return candidato
