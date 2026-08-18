"""Export dei risultati in BibTeX e CSV."""

from __future__ import annotations

import csv
import io
import re
import unicodedata

from .models import Work

# Campi selezionabili per la tabella e per gli export.
CAMPI = ("anno", "titolo", "autori", "sede", "doi", "url", "abstract", "fonti", "pdf")
CAMPI_PREDEFINITI = ("anno", "titolo", "autori", "sede", "fonti")

_ATTRIBUTI = {
    "anno": "year",
    "titolo": "title",
    "autori": "authors",
    "sede": "venue",
    "doi": "doi",
    "url": "url",
    "abstract": "abstract",
    "fonti": "sources",
    "pdf": "oa_url",
}

_NON_WORD = re.compile(r"[^a-z0-9]+")
_STOPWORDS = {"the", "a", "an", "of", "on", "in", "and", "for", "il", "lo", "la", "di", "e"}


def cite_key(work: Work, taken: set[str]) -> str:
    author = work.authors[0].split()[-1].lower() if work.authors else "anon"
    author = _ascii(author) or "anon"
    year = str(work.year or "s.d.").replace(".", "")
    word = ""
    for candidate in _NON_WORD.split(_ascii(work.title.lower())):
        if candidate and candidate not in _STOPWORDS:
            word = candidate
            break
    base = f"{author}{year}{word}"[:40] or "ref"
    key, suffix = base, ord("a")
    while key in taken:
        key = f"{base}{chr(suffix)}"
        suffix += 1
    taken.add(key)
    return key


def normalizza_campi(campi=None) -> list[str]:
    scelti = [c for c in (campi or []) if c in CAMPI]
    return scelti or list(CAMPI_PREDEFINITI)


def valore(work: Work, campo: str):
    dato = getattr(work, _ATTRIBUTI[campo], None)
    if isinstance(dato, list):
        return "; ".join(dato)
    return dato


def to_bibtex(works: list[Work], campi=None) -> str:
    """Il titolo c'è sempre; gli altri campi seguono la selezione."""

    campi = normalizza_campi(campi)
    corrispondenze = [
        ("autori", "author", lambda w: " and ".join(w.authors)),
        ("anno", "year", lambda w: str(w.year or "")),
        ("sede", "journal", lambda w: w.venue or ""),
        ("doi", "doi", lambda w: w.doi or ""),
        ("url", "url", lambda w: w.url or ""),
        ("abstract", "abstract", lambda w: w.abstract or ""),
        ("pdf", "file", lambda w: w.oa_url or ""),
    ]
    taken: set[str] = set()
    entries = []
    for work in works:
        fields = [("title", work.title)]
        for campo, nome_bib, estrai in corrispondenze:
            if campo in campi and estrai(work):
                fields.append((nome_bib, estrai(work)))
        body = ",\n".join(f"  {name} = {{{_clean(value)}}}" for name, value in fields)
        entries.append(f"@article{{{cite_key(work, taken)},\n{body}\n}}")
    return "\n\n".join(entries) + ("\n" if entries else "")


def to_csv(works: list[Work], campi=None) -> str:
    campi = normalizza_campi(campi)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(campi)
    for work in works:
        writer.writerow([valore(work, campo) or "" for campo in campi])
    return buffer.getvalue()


def apa_autore(nome: str) -> str:
    """«Duri Long» → «Long, D.»; «Yang Z» (stile PubMed) → «Yang, Z.»."""

    parti = [p for p in nome.replace(",", " ").split() if p]
    if not parti:
        return ""
    if len(parti) == 1:
        return parti[0]
    ultimo = parti[-1]
    if len(ultimo) <= 3 and ultimo.isupper():
        cognome = " ".join(parti[:-1])
        iniziali = " ".join(f"{lettera}." for lettera in ultimo)
        return f"{cognome}, {iniziali}"
    cognome = ultimo
    iniziali = " ".join(f"{p[0].upper()}." for p in parti[:-1] if p)
    return f"{cognome}, {iniziali}" if iniziali else cognome


def apa_autori(autori: list[str]) -> str:
    nomi = [apa_autore(a) for a in autori if a.strip()]
    if not nomi:
        return ""
    if len(nomi) == 1:
        return nomi[0]
    if len(nomi) > 20:
        return ", ".join(nomi[:19]) + ", ... " + nomi[-1]
    return ", ".join(nomi[:-1]) + ", & " + nomi[-1]


def apa(work: Work) -> str:
    """Riferimento in stile APA 7. I dati mancanti vengono semplicemente omessi."""

    pezzi = []
    autori = apa_autori(work.authors)
    if autori:
        pezzi.append(autori if autori.endswith(".") else autori + ".")
    pezzi.append(f"({work.year}).") if work.year else pezzi.append("(s.d.).")
    titolo = work.title.strip().rstrip(".")
    pezzi.append(f"{titolo}.")
    if work.venue:
        pezzi.append(f"{work.venue}.")
    if work.doi:
        doi = work.doi if work.doi.startswith("http") else f"https://doi.org/{work.doi}"
        pezzi.append(doi)
    elif work.url:
        pezzi.append(work.url)
    return " ".join(pezzi)


def to_apa(works: list[Work]) -> str:
    """Elenco ordinato alfabeticamente, come vuole la lista dei riferimenti."""

    righe = sorted((apa(w) for w in works), key=lambda r: r.lower())
    return "\n\n".join(righe) + ("\n" if righe else "")


def _clean(value: str) -> str:
    return str(value).replace("{", "").replace("}", "").strip()


def _ascii(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    return "".join(c for c in text if not unicodedata.combining(c) and c.isascii())
