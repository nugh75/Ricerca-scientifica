"""Scaricamento dei PDF ad accesso aperto in ~/.ricerca/pdf.

Solo i record che portano un link aperto (`oa_url`) sono scaricabili: qui non
si aggira nessun paywall.
"""

from __future__ import annotations

import io
import json
import re
import unicodedata
import zipfile

import httpx

from . import biblioteca
from . import config as config_module
from .export import cite_key, cognome
from .models import Work
from .i18n import strings
from .registro import annota

MAX_BYTE = 60 * 1024 * 1024
_NON_FILE = re.compile(r"[^A-Za-z0-9._-]+")


def cartella():
    percorso = config_module.CONFIG_DIR / "pdf"
    percorso.mkdir(parents=True, exist_ok=True)
    return percorso


def _senza_accenti(testo: str) -> str:
    scomposto = unicodedata.normalize("NFKD", testo)
    return "".join(c for c in scomposto if not unicodedata.combining(c))


def _pezzo(testo: str, massimo: int) -> str:
    pulito = _NON_FILE.sub("-", _senza_accenti(testo).lower()).strip("-")
    pulito = re.sub(r"-{2,}", "-", pulito)
    return pulito[:massimo].strip("-")


def nome_file(work: Work) -> str:
    """anno_autori_titolo: leggibile in una cartella, ordinabile per anno."""

    anno = str(work.year or "sd")
    cognomi = [cognome(nome) for nome in work.authors[:3] if cognome(nome)]
    autori = "-".join(_pezzo(c, 20) for c in cognomi) or "anon"
    if len(work.authors) > 3:
        autori += "-et-al"
    titolo = _pezzo(work.title, 70) or "senza-titolo"
    return f"{anno}_{autori}_{titolo}.pdf"


def _nome_storico(work: Work) -> str:
    """Il nome usato fino alla 1.14: serve a non riscaricare i vecchi file."""

    import hashlib

    chiave = _NON_FILE.sub("-", cite_key(work, set()))
    firma = hashlib.sha1((work.doi or work.title).encode("utf-8")).hexdigest()[:6]
    return f"{chiave}-{firma}.pdf"


def _firma(work: Work) -> str:
    """Che cosa distingue un lavoro da un altro, per l'indice dei file."""

    from .dedup import normalize_doi, normalize_title

    doi = normalize_doi(work.doi)
    return f"doi:{doi}" if doi else f"titolo:{normalize_title(work.title)}|{work.year or ''}"


def _percorso_indice():
    """L'indice dei nomi, traslocando quello col nome vecchio."""

    cartella_pdf = config_module.CONFIG_DIR / "pdf"
    percorso = cartella_pdf / "index.json"
    storico = cartella_pdf / "indice.json"
    if storico.exists() and not percorso.exists():
        storico.rename(percorso)
    return percorso


def _indice() -> dict:
    percorso = _percorso_indice()
    if not percorso.exists():
        return {}
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return dati if isinstance(dati, dict) else {}


def _annota(work: Work, nome: str) -> None:
    dati = _indice()
    dati[_firma(work)] = nome
    percorso = _percorso_indice()
    percorso.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")


def nome_libero(work: Work) -> str:
    """Il nome leggibile, con un numero in coda solo se già occupato.

    Due lavori diversi possono avere anno, autori e titolo uguali: senza
    questo controllo il secondo sovrascriverebbe il primo.
    """

    cartella_pdf = config_module.CONFIG_DIR / "pdf"
    annotato = _indice().get(_firma(work))
    if annotato:
        return annotato

    base = nome_file(work)
    if not (cartella_pdf / base).exists():
        return base
    gambo = base[: -len(".pdf")]
    numero = 2
    while (cartella_pdf / f"{gambo}-{numero}.pdf").exists():
        numero += 1
    return f"{gambo}-{numero}.pdf"


def gia_scaricato(work: Work):
    cartella_pdf = config_module.CONFIG_DIR / "pdf"
    annotato = _indice().get(_firma(work))
    if annotato and (cartella_pdf / annotato).exists():
        return cartella_pdf / annotato

    # Il file col nome «naturale» vale solo se non appartiene già a un altro
    # lavoro: due omonimi con DOI diversi devono restare due file distinti.
    percorso = cartella_pdf / nome_file(work)
    if percorso.exists() and percorso.name not in set(_indice().values()):
        return percorso

    storico = cartella_pdf / _nome_storico(work)
    if storico.exists():
        # Un file scaricato prima del cambio di nome: si rinomina, così la
        # cartella diventa leggibile senza riscaricare nulla.
        storico.rename(percorso)
        testo_storico = storico.with_suffix(".txt")
        if testo_storico.exists():
            testo_storico.rename(percorso.with_suffix(".txt"))
        _annota(work, percorso.name)
        return percorso
    return None


async def scarica(work: Work, client: httpx.AsyncClient):
    """Scarica il PDF aperto del record. Solleva se il file non è un PDF."""

    if not work.oa_url:
        raise ValueError("nessun link ad accesso aperto")

    esistente = gia_scaricato(work)
    if esistente:
        return esistente

    response = await client.get(work.oa_url, timeout=60, follow_redirects=True)
    response.raise_for_status()
    contenuto = response.content
    if not contenuto.startswith(b"%PDF"):
        raise ValueError("la risposta non è un PDF")
    if len(contenuto) > MAX_BYTE:
        raise ValueError("file troppo grande")

    percorso = cartella() / nome_libero(work)
    percorso.write_bytes(contenuto)
    _annota(work, percorso.name)
    annota(
        strings(config_module.load().lang)["log_pdf_saved"],
        f"{percorso.name} · {len(contenuto) // 1024} KB",
    )
    biblioteca.estrai(percorso)  # il testo serve per cercare dentro i PDF
    return percorso


def archivio(works: list[Work]) -> tuple[bytes, int]:
    """Uno zip con i PDF già scaricati dei record indicati."""

    buffer = io.BytesIO()
    quanti = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for work in works:
            percorso = gia_scaricato(work)
            if percorso is None:
                continue
            zip_file.write(percorso, arcname=percorso.name)
            quanti += 1
    return buffer.getvalue(), quanti


def quanti_scaricati(works: list[Work]) -> int:
    return sum(1 for work in works if gia_scaricato(work))
