"""Export dei risultati in BibTeX e CSV."""

from __future__ import annotations

import csv
import io
import re
import unicodedata

from .models import Work

# Campi selezionabili per la tabella e per gli export.
CAMPI = (
    "anno", "titolo", "autori", "sede", "doi", "url", "abstract", "fonti", "pdf",
    "citazioni", "ritirato", "decisione", "motivo", "nota",
)
CAMPI_PREDEFINITI = ("anno", "titolo", "autori", "sede", "citazioni", "fonti")

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
    "citazioni": "citazioni",
    "ritirato": "ritirato",
    "decisione": "decisione",
    "motivo": "motivo",
    "nota": "nota",
}

_NON_WORD = re.compile(r"[^a-z0-9]+")
_STOPWORDS = {"the", "a", "an", "of", "on", "in", "and", "for", "il", "lo", "la", "di", "e"}


def cognome(nome: str) -> str:
    """«Duri Long» → Long; «Rossi M» (stile PubMed) → Rossi.

    Prendere sempre l'ultimo pezzo darebbe «M» come cognome, e chiavi di
    citazione come `m2024studio`.
    """

    parti = [p for p in nome.replace(",", " ").split() if p]
    if not parti:
        return ""
    ultimo = parti[-1]
    if len(parti) > 1 and len(ultimo) <= 3 and ultimo.isupper():
        return " ".join(parti[:-1])
    return ultimo


def cite_key(work: Work, taken: set[str]) -> str:
    author = cognome(work.authors[0]).lower() if work.authors else "anon"
    author = _NON_WORD.sub("", _ascii(author)) or "anon"
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
        # Solo `None` diventa cella vuota: uno zero o un `False` sono un dato,
        # non un'assenza, e una revisione sistematica non deve confonderli.
        writer.writerow([v if (v := valore(work, campo)) is not None else "" for campo in campi])
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
        iniziali = " ".join(f"{lettera}." for lettera in ultimo)
        return f"{' '.join(parti[:-1])}, {iniziali}"
    iniziali = " ".join(f"{p[0].upper()}." for p in parti[:-1] if p)
    return f"{ultimo}, {iniziali}" if iniziali else ultimo


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


def protocollo(voce: dict, conteggi: dict) -> str:
    """Tabella per la sezione «Metodo»: data, motore, stringa, risultati."""

    quando = str(voce.get("quando", "")).replace("T", " ")
    righe = [
        f"# Protocollo di ricerca — {voce.get('topic') or 's.t.'}",
        "",
        f"Data della ricerca: {quando}",
        "",
        "## Blocchi concettuali",
        "",
    ]
    campione = (voce.get("filtri") or {}).get("campione")
    if campione:
        seme = (voce.get("filtri") or {}).get("seme") or "—"
        righe[3:3] = [f"Campione casuale: {campione} record, seme {seme}"]
    for blocco in voce.get("blocchi", []):
        righe.append(f"- **{blocco.get('label', '')}**: " + ", ".join(blocco.get("terms", [])))
    if voce.get("mesh"):
        righe.append("- **MeSH**: " + ", ".join(voce["mesh"]))

    attivi = [
        f"{k}: {v}" for k, v in (voce.get("filtri") or {}).items()
        if k not in ("campione", "seme") and v not in (None, False, "")
    ]
    if attivi:
        righe += ["", "## Filtri", ""] + [f"- {riga}" for riga in attivi]

    righe += ["", "## Interrogazioni", "", "| Banca dati | Stringa | Risultati |", "|---|---|---|"]
    for fonte in voce.get("fonti", []):
        esito = fonte.get("errore") or fonte.get("trovati", 0)
        stringa = str(fonte.get("query", "")).replace("|", "\\|")
        righe.append(f"| {fonte.get('etichetta', '')} | `{stringa}` | {esito} |")

    oql = [f for f in voce.get("fonti", []) if f.get("oql")]
    if oql:
        righe += ["", "## Query OQL (OpenAlex)", ""]
        righe += [f"- **{f.get('etichetta', '')}**: `{f['oql']}`" for f in oql]

    righe += [
        "",
        "## Selezione",
        "",
        f"- record recuperati: {conteggi.get('grezzi', 0)}",
        f"- duplicati rimossi: {conteggi.get('duplicati', 0)}",
        f"- record esaminati: {conteggi.get('dopo_deduplica', 0)}",
        f"- inclusi: {conteggi.get('incluso', 0)}",
        f"- da valutare: {conteggi.get('forse', 0)}",
        f"- esclusi: {conteggi.get('escluso', 0)}",
        f"- non ancora valutati: {conteggi.get('da_valutare', 0)}",
        "",
    ]
    return "\n".join(righe)


def protocollo_testo(voce: dict, conteggi: dict) -> str:
    """Lo stesso protocollo senza marcatura: si incolla ovunque."""

    righe = [
        f"PROTOCOLLO DI RICERCA — {voce.get('topic') or 's.t.'}",
        "",
        f"Data della ricerca: {str(voce.get('quando', '')).replace('T', ' ')}",
        "",
        "BLOCCHI CONCETTUALI",
    ]
    campione = (voce.get("filtri") or {}).get("campione")
    if campione:
        seme = (voce.get("filtri") or {}).get("seme") or "—"
        righe[3:3] = [f"Campione casuale: {campione} record, seme {seme}"]
    for blocco in voce.get("blocchi", []):
        righe.append(f"  {blocco.get('label', '')}: " + ", ".join(blocco.get("terms", [])))
    if voce.get("mesh"):
        righe.append("  MeSH: " + ", ".join(voce["mesh"]))

    attivi = [
        f"{k}: {v}" for k, v in (voce.get("filtri") or {}).items()
        if k not in ("campione", "seme") and v not in (None, False, "")
    ]
    if attivi:
        righe += ["", "FILTRI"] + [f"  {riga}" for riga in attivi]

    righe += ["", "INTERROGAZIONI"]
    for fonte in voce.get("fonti", []):
        esito = fonte.get("errore") or f"{fonte.get('trovati', 0)} risultati"
        righe.append(f"  {fonte.get('etichetta', '')} — {esito}")
        righe.append(f"    {fonte.get('query', '')}")

    oql = [f for f in voce.get("fonti", []) if f.get("oql")]
    if oql:
        righe += ["", "QUERY OQL (OPENALEX)"]
        righe += [f"  {f.get('etichetta', '')}: {f['oql']}" for f in oql]

    righe += [
        "",
        "SELEZIONE",
        f"  record recuperati:      {conteggi.get('grezzi', 0)}",
        f"  duplicati rimossi:      {conteggi.get('duplicati', 0)}",
        f"  record esaminati:       {conteggi.get('dopo_deduplica', 0)}",
        f"  inclusi:                {conteggi.get('incluso', 0)}",
        f"  da valutare:            {conteggi.get('forse', 0)}",
        f"  esclusi:                {conteggi.get('escluso', 0)}",
        f"  non ancora valutati:    {conteggi.get('da_valutare', 0)}",
        "",
    ]
    return "\n".join(righe)
