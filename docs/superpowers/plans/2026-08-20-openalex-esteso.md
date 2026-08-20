# OpenAlex esteso — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Portare dentro Ricerca le funzioni dell'API OpenAlex che servono a una revisione della letteratura — record arricchito, filtri veri, PDF dall'archivio, snowballing, faccette, ricerca semantica, autocomplete, OQL nel protocollo — con la spesa contata a schermo.

**Architecture:** Un modulo unico (`ricerca/openalex_api.py`) diventa l'unica porta verso `api.openalex.org`: costruisce i parametri (chiave, `mailto`), esegue la GET e annota `meta.cost_usd` nel registro del giorno (`ricerca/costo.py`). Sopra ci si appoggiano la fonte esistente, la raccolta dei termini e i quattro moduli nuovi (`citazioni.py`, `faccette.py`, la fonte semantica, l'autocomplete). Nessuna dipendenza nuova, nessun cambio di architettura: FastAPI rende HTML, htmx sostituisce i pezzi.

**Tech Stack:** Python ≥ 3.11, FastAPI, httpx asincrono, Jinja2, htmx, pytest + pytest-asyncio (`asyncio_mode = auto`) + respx.

**Spec:** `docs/specs/2026-08-20-openalex-esteso.md`

## Global Constraints

- Nessuna dipendenza nuova: solo quelle già in `pyproject.toml`.
- Python ≥ 3.11. httpx asincrono ovunque; nessuna chiamata bloccante nelle rotte.
- Ogni stringa a schermo va in `ricerca/i18n.py` in **entrambe** le lingue: `tests/test_i18n.py::test_le_due_lingue_hanno_le_stesse_chiavi` fallisce se una chiave manca.
- Nomi di funzioni, variabili, commenti e docstring **in italiano**, come il resto del programma. I nomi dei campi dell'API OpenAlex restano in inglese.
- I test usano `respx` per fingere le risposte HTTP: nessun test della suite normale tocca la rete. I test che interrogano l'API vera vanno in `tests/contratto/` con `@pytest.mark.rete`.
- La cache è spenta nei test (`conftest.py`, fixture `cache_spenta`).
- Costi verificati il 2026-08-20: entità singola $0, lista/filtro $0.0001, ricerca e semantica $0.001, autocomplete $0, PDF dall'archivio $0.01. Budget quotidiano $1.00 con chiave, $0.10 senza.
- Nessuna chiamata a pagamento (il PDF dall'archivio) parte senza che l'opzione sia stata accesa a mano.
- `git commit` a ogni task, mai `git push` senza che lo chieda chi conduce il lavoro.

## Struttura dei file

**Nuovi:**
- `ricerca/costo.py` — registro del credito OpenAlex speso, giorno per giorno.
- `ricerca/openalex_api.py` — l'unico punto di contatto con l'API: parametri, chiamata, costo, utilità (`id_breve`, `abstract_da_indice`, `oql`).
- `ricerca/citazioni.py` — snowballing nelle tre direzioni.
- `ricerca/faccette.py` — profilo del campo con `group_by`.
- `ricerca/sources/openalex_semantica.py` — la fonte che cerca per significato.
- `ricerca/templates/partials/citazioni.html`, `faccette.html`, `credito.html`.

**Modificati:** `cache.py` (marcatore), `models.py` (campi di `Work` e `Filtri`), `dedup.py` (fusione dei campi nuovi), `sources/openalex.py` (riscritta sul modulo comune), `keywords.py` (idem), `pdf.py` (ultimo tentativo), `history.py` (OQL e aggiunta di record), `export.py` (colonne e protocollo), `strategy.py` (filtri dal modulo), `app.py` (rotte nuove), `config.py` (opzione dell'archivio), `i18n.py` (stringhe), i template della strategia e della scheda.

## Fasi

Le quattro fasi sono indipendenti fra loro e ognuna lascia il programma funzionante. La 1 è il presupposto delle altre tre.

| Fase | Task | Che cosa consegna |
|---|---|---|
| 1 — fondamenta | 1–5 | costo contato, record ricco, filtri veri, OQL nel protocollo |
| 2 — PDF | 6 | copia dall'archivio OpenAlex quando tutto il resto fallisce |
| 3 — snowballing | 7–8 | citazioni avanti, indietro e di lato, aggiunte alla ricerca |
| 4 — esplorazione | 9–13 | faccette, ricerca semantica, autocomplete, filtri per entità, campione |

---

# Fase 1 — fondamenta

### Task 1: Registro del credito speso

**Files:**
- Create: `ricerca/costo.py`
- Modify: `ricerca/cache.py:88-110` (marcatore sulle risposte servite dalla cache)
- Test: `tests/test_costo.py`

**Interfaces:**
- Produces: `costo.aggiungi(usd: float, quando: str = "") -> float`, `costo.speso(quando: str = "") -> float`, `costo.budget(config: Config) -> float`, `costo.resta(config: Config) -> float`, `costo.COSTO_PDF: float`; `cache.INTESTAZIONE: str`.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `tests/test_costo.py`:

```python
from ricerca import costo
from ricerca.config import Config


def test_le_spese_si_sommano_nel_giorno():
    costo.aggiungi(0.001, "2026-08-20")
    costo.aggiungi(0.0001, "2026-08-20")
    assert costo.speso("2026-08-20") == 0.0011


def test_i_giorni_restano_separati():
    costo.aggiungi(0.5, "2026-08-19")
    costo.aggiungi(0.25, "2026-08-20")
    assert costo.speso("2026-08-19") == 0.5
    assert costo.speso("2026-08-20") == 0.25


def test_una_spesa_nulla_non_scrive_nulla():
    costo.aggiungi(0.0, "2026-08-20")
    assert costo.speso("2026-08-20") == 0.0


def test_il_budget_dipende_dalla_chiave():
    assert costo.budget(Config()) == 0.10
    assert costo.budget(Config(openalex_api_key="k")) == 1.00


def test_quanto_resta_non_va_sotto_zero():
    costo.aggiungi(0.4, costo.oggi())
    assert costo.resta(Config()) == 0.0
    assert costo.resta(Config(openalex_api_key="k")) == 0.6


def test_un_file_illeggibile_non_ferma_il_programma(isolated_config):
    (isolated_config / "openalex-costo.json").write_text("{rotto", encoding="utf-8")
    assert costo.speso("2026-08-20") == 0.0
    assert costo.aggiungi(0.001, "2026-08-20") == 0.001
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Esegui: `python -m pytest tests/test_costo.py -v`
Atteso: FAIL con `ModuleNotFoundError: No module named 'ricerca.costo'`.

- [ ] **Step 3: Scrivi `ricerca/costo.py`**

```python
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
```

- [ ] **Step 4: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_costo.py -v`
Atteso: PASS, sei test.

- [ ] **Step 5: Scrivi il test del marcatore di cache**

Aggiungi in `tests/test_cache.py`:

```python
@respx.mock
async def test_la_risposta_dalla_cache_si_riconosce(monkeypatch):
    monkeypatch.setenv("RICERCA_CACHE", "1")
    respx.get("https://esempio.test/x").mock(return_value=httpx.Response(200, json={"a": 1}))
    async with cache.client() as client:
        prima = await client.get("https://esempio.test/x")
        dopo = await client.get("https://esempio.test/x")
    assert cache.INTESTAZIONE not in prima.headers
    assert dopo.headers.get(cache.INTESTAZIONE) == "1"
```

Verifica che in cima a `tests/test_cache.py` ci siano già `import httpx`, `import respx` e `from ricerca import cache`; aggiungi quelli che mancano.

- [ ] **Step 6: Esegui il test e verifica che fallisca**

Esegui: `python -m pytest tests/test_cache.py -v`
Atteso: FAIL con `AttributeError: module 'ricerca.cache' has no attribute 'INTESTAZIONE'`.

- [ ] **Step 7: Metti il marcatore in `ricerca/cache.py`**

Sotto `VARIABILE = "RICERCA_CACHE"` aggiungi:

```python
# Le risposte servite dalla cache portano questo marcatore: il costo OpenAlex
# si conta una volta sola, non a ogni ripetizione della stessa query.
INTESTAZIONE = "x-ricerca-cache"
```

Dentro `TrasportoConCache.handle_async_request`, la riga che serve la copia salvata diventa:

```python
        if salvata is not None:
            stato, tipo, corpo = salvata
            return httpx.Response(
                stato, content=corpo, headers={"content-type": tipo, INTESTAZIONE: "1"}
            )
```

- [ ] **Step 8: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_cache.py tests/test_costo.py -v`
Atteso: PASS.

- [ ] **Step 9: Commit**

```bash
git add ricerca/costo.py ricerca/cache.py tests/test_costo.py tests/test_cache.py
git commit -m "feat: tiene il conto del credito OpenAlex speso ogni giorno"
```

---

### Task 2: Un solo punto di contatto con OpenAlex

**Files:**
- Create: `ricerca/openalex_api.py`
- Modify: `ricerca/sources/openalex.py` (tutta), `ricerca/keywords.py:141-156`
- Test: `tests/test_openalex_api.py`

**Interfaces:**
- Consumes: `costo.aggiungi`, `cache.INTESTAZIONE` (Task 1).
- Produces:
  - `openalex_api.API: str`, `openalex_api.CONTENUTI: str`
  - `openalex_api.parametri(config: Config, **extra) -> dict[str, str]`
  - `openalex_api.chiama(client: httpx.AsyncClient, percorso: str, config: Config, timeout: float = 25, **extra) -> dict`
  - `openalex_api.id_breve(valore: str | None) -> str`
  - `openalex_api.abstract_da_indice(indice: dict | None) -> str | None`
  - `openalex_api.oql(corpo: dict) -> str`
  - `openalex_api.ULTIMA_OQL: ContextVar[str]` — l'OQL dell'ultima chiamata *di questo compito*. Una variabile di contesto e non un attributo della fonte perché le fonti nel registro sono istanze uniche e due ricerche in parallelo si sovrascriverebbero il valore a vicenda; `asyncio.gather` dà a ogni compito la sua copia del contesto.

- [ ] **Step 1: Scrivi i test che falliscono**

Crea `tests/test_openalex_api.py`:

```python
import httpx
import respx

from ricerca import costo, openalex_api
from ricerca.config import Config


@respx.mock
async def test_la_chiamata_porta_chiave_ed_email():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"meta": {}, "results": []})
    )
    async with httpx.AsyncClient() as client:
        await openalex_api.chiama(
            client, "/works", Config(mailto="a@b.it", openalex_api_key="k"), filter="type:article"
        )
    indirizzo = str(rotta.calls[0].request.url)
    assert "api_key=k" in indirizzo
    assert "mailto=a%40b.it" in indirizzo
    assert "filter=type%3Aarticle" in indirizzo


@respx.mock
async def test_i_parametri_vuoti_non_partono():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"meta": {}, "results": []})
    )
    async with httpx.AsyncClient() as client:
        await openalex_api.chiama(client, "/works", Config(), search="", per_page="5")
    indirizzo = str(rotta.calls[0].request.url)
    assert "search=" not in indirizzo
    assert "mailto" not in indirizzo


@respx.mock
async def test_il_costo_dichiarato_finisce_nel_registro():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"meta": {"cost_usd": 0.001}, "results": []})
    )
    async with httpx.AsyncClient() as client:
        await openalex_api.chiama(client, "/works", Config())
    assert costo.speso() == 0.001


@respx.mock
async def test_una_risposta_dalla_cache_non_si_conta():
    from ricerca import cache

    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(
            200, json={"meta": {"cost_usd": 0.001}}, headers={cache.INTESTAZIONE: "1"}
        )
    )
    async with httpx.AsyncClient() as client:
        await openalex_api.chiama(client, "/works", Config())
    assert costo.speso() == 0.0


@respx.mock
async def test_un_errore_arriva_al_chiamante():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(429, json={"message": "budget finito"})
    )
    async with httpx.AsyncClient() as client:
        try:
            await openalex_api.chiama(client, "/works", Config())
        except httpx.HTTPStatusError as exc:
            assert exc.response.status_code == 429
        else:
            raise AssertionError("doveva sollevare")


def test_l_identificativo_si_accorcia():
    assert openalex_api.id_breve("https://openalex.org/W2741809807") == "W2741809807"
    assert openalex_api.id_breve("W123") == "W123"
    assert openalex_api.id_breve(None) == ""


def test_l_abstract_si_rimonta_dall_indice():
    indice = {"Il": [0], "gatto": [1, 4], "sul": [2], "tetto": [3], "dorme": [5]}
    assert openalex_api.abstract_da_indice(indice) == "Il gatto sul tetto gatto dorme"
    assert openalex_api.abstract_da_indice(None) is None
    assert openalex_api.abstract_da_indice({}) is None


def test_l_oql_si_legge_dalla_risposta():
    corpo = {"meta": {"x_query": {"oql": "works where year is (2024)"}}}
    assert openalex_api.oql(corpo) == "works where year is (2024)"
    assert openalex_api.oql({"meta": {}}) == ""
    assert openalex_api.oql({}) == ""


@respx.mock
async def test_l_oql_resta_nel_contesto_del_compito():
    import asyncio

    respx.get(url__startswith="https://api.openalex.org/works").mock(
        side_effect=lambda richiesta: httpx.Response(200, json={
            "meta": {"x_query": {"oql": str(richiesta.url.params.get("filter"))}}, "results": [],
        })
    )

    async def chiama_e_leggi(quale: str) -> str:
        async with httpx.AsyncClient() as client:
            await openalex_api.chiama(client, "/works", Config(), filter=quale)
        return openalex_api.ULTIMA_OQL.get("")

    uno, due = await asyncio.gather(chiama_e_leggi("uno"), chiama_e_leggi("due"))
    assert uno == "uno"
    assert due == "due"
```

- [ ] **Step 2: Esegui i test e verifica che falliscano**

Esegui: `python -m pytest tests/test_openalex_api.py -v`
Atteso: FAIL con `ModuleNotFoundError: No module named 'ricerca.openalex_api'`.

- [ ] **Step 3: Scrivi `ricerca/openalex_api.py`**

```python
"""L'unico punto da cui l'applicazione parla con OpenAlex.

Chiave, email di cortesia, timeout e contabilità del costo stanno scritti qui
una volta sola: le funzioni che si appoggiano a OpenAlex — la fonte, i
suggerimenti, le citazioni, le faccette — non li riscrivono ognuna a modo suo.
"""

from __future__ import annotations

from contextvars import ContextVar

import httpx

from . import cache, costo
from .config import Config

API = "https://api.openalex.org"
CONTENUTI = "https://content.openalex.org"

# L'interrogazione riscritta da OpenAlex nel suo linguaggio, per il compito in
# corso. Non un attributo della fonte: nel registro le fonti sono istanze
# uniche e due ricerche avviate insieme si sovrascriverebbero il valore.
# `asyncio.gather` dà a ogni compito la sua copia del contesto, quindi qui
# ognuno legge il proprio.
ULTIMA_OQL: ContextVar[str] = ContextVar("ultima_oql", default="")


def parametri(config: Config, **extra) -> dict[str, str]:
    """I parametri della chiamata, senza i vuoti: OpenAlex rifiuta con `400`
    un `search=` senza contenuto e un `mailto` malformato."""

    params = {chiave: str(valore) for chiave, valore in extra.items() if valore not in ("", None)}
    if config.mailto_valido:
        params["mailto"] = config.mailto_valido
    if config.openalex_api_key:
        params["api_key"] = config.openalex_api_key
    return params


async def chiama(
    client: httpx.AsyncClient,
    percorso: str,
    config: Config,
    timeout: float = 25,
    **extra,
) -> dict:
    """Una GET su OpenAlex, con la spesa annotata nel registro del giorno.

    Le risposte che arrivano dalla cache portano il marcatore e non si
    contano: la stessa query ripetuta mentre si affina una strategia si paga
    una volta sola.
    """

    risposta = await client.get(
        f"{API}{percorso}", params=parametri(config, **extra), timeout=timeout
    )
    risposta.raise_for_status()
    corpo = risposta.json()
    if not risposta.headers.get(cache.INTESTAZIONE):
        speso = (corpo.get("meta") or {}).get("cost_usd") or 0.0
        costo.aggiungi(float(speso))
    scritta = oql(corpo)
    if scritta:
        ULTIMA_OQL.set(scritta)
    return corpo


def id_breve(valore: str | None) -> str:
    """`https://openalex.org/W123` → `W123`: il filtro vuole la forma corta."""

    return str(valore or "").rstrip("/").rsplit("/", 1)[-1]


def abstract_da_indice(indice: dict | None) -> str | None:
    """OpenAlex consegna l'abstract smontato in parola → posizioni.

    Rimontarlo non costa una chiamata in più e riempie una scheda che
    altrimenti resta muta.
    """

    if not indice:
        return None
    posizioni: list[tuple[int, str]] = []
    for parola, dove in indice.items():
        posizioni.extend((posto, parola) for posto in dove or [])
    if not posizioni:
        return None
    posizioni.sort()
    return " ".join(parola for _, parola in posizioni) or None


def oql(corpo: dict) -> str:
    """La query riscritta da OpenAlex nel suo linguaggio: la strategia
    riproducibile che una revisione deve poter pubblicare."""

    return str((((corpo.get("meta") or {}).get("x_query")) or {}).get("oql") or "")
```

- [ ] **Step 4: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_openalex_api.py -v`
Atteso: PASS, otto test.

- [ ] **Step 5: Riscrivi `ricerca/sources/openalex.py` sul modulo comune**

Sostituisci il corpo di `search` e rendi pubblica la costruzione del record (serve a `citazioni.py` e alla fonte semantica). Il file diventa:

```python
from __future__ import annotations

import httpx

from .. import openalex_api
from ..config import Config
from ..i18n import strings
from ..models import Work
from .base import Source, clean

# Tutto quello che serve al programma, in una sola chiamata: l'abstract, lo
# stato di ritiro, le citazioni e la copia nell'archivio non costano di più.
SELECT = (
    "id,doi,title,publication_year,authorships,primary_location,best_oa_location,"
    "open_access,locations,abstract_inverted_index,is_retracted,cited_by_count,"
    "citation_normalized_percentile,has_content,content_urls,language"
)


class OpenAlex(Source):
    id = "openalex"
    label = "OpenAlex"
    homepage = "https://openalex.org"

    def avviso(self, config: Config, lang: str | None = None) -> str | None:
        # Senza chiave si finisce nella corsia anonima, limitata e a budget.
        return None if config.openalex_api_key else strings(lang)["openalex_budget"]

    async def search(self, client: httpx.AsyncClient, query: str, limit: int, config: Config, filtri=None):
        corpo = await openalex_api.chiama(
            client,
            "/works",
            config,
            filter=filtro(query, filtri),
            per_page=str(min(limit, 50)),
            select=SELECT,
        )
        return [work_da(item) for item in corpo.get("results", [])]


def filtro(query: str, filtri=None) -> str:
    pezzi = [f"title_and_abstract.search:{query}"]
    if filtri and filtri.anno_da:
        pezzi.append(f"from_publication_date:{filtri.anno_da}-01-01")
    if filtri and filtri.anno_a:
        pezzi.append(f"to_publication_date:{filtri.anno_a}-12-31")
    if filtri and filtri.solo_articoli:
        pezzi.append("type:article")
    return ",".join(pezzi)


def _pdf_candidati(item: dict) -> list[str]:
    """Il PDF migliore prima, poi le altre copie, infine il collegamento di
    accesso aperto — che a volte è già il file, a volte una pagina."""

    candidati = []
    for luogo in [item.get("best_oa_location"), *(item.get("locations") or [])]:
        indirizzo = (luogo or {}).get("pdf_url")
        if indirizzo:
            candidati.append(indirizzo)
    aperto = (item.get("open_access") or {}).get("oa_url")
    if aperto:
        candidati.append(aperto)
    return candidati


def work_da(item: dict) -> Work:
    location = item.get("primary_location") or {}
    venue = (location.get("source") or {}).get("display_name")
    candidati = _pdf_candidati(item)
    percentile = item.get("citation_normalized_percentile") or {}
    return Work(
        title=clean(item.get("title")) or "(senza titolo)",
        authors=[
            a["author"]["display_name"]
            for a in item.get("authorships", [])
            if a.get("author", {}).get("display_name")
        ],
        year=item.get("publication_year"),
        doi=clean(item.get("doi")),
        venue=clean(venue),
        url=clean(item.get("id")),
        abstract=openalex_api.abstract_da_indice(item.get("abstract_inverted_index")),
        oa_url=candidati[0] if candidati else None,
        oa_urls=candidati[1:],
        sources=["openalex"],
        openalex_id=openalex_api.id_breve(item.get("id")),
        ritirato=bool(item.get("is_retracted")),
        citazioni=item.get("cited_by_count"),
        molto_citato=bool(percentile.get("is_in_top_10_percent")),
        pdf_archivio=str((item.get("content_urls") or {}).get("pdf") or ""),
    )
```

I campi nuovi di `Work` arrivano nel Task 3: fino a lì questo file non importa (l'attributo non esiste ancora). **Esegui il Task 3 subito dopo, nella stessa sessione**, oppure inverti l'ordine dei due task.

- [ ] **Step 6: Riscrivi `_openalex` in `ricerca/keywords.py`**

Sostituisci il corpo della funzione (righe 141-156, dal `params = {...}` fino a `risultati = ...`) con:

```python
    from . import openalex_api

    corpo = await openalex_api.chiama(
        client, "/works", config, search=topic, per_page="50", select="title,topics,keywords"
    )
    risultati = corpo.get("results", [])
```

Togli la costante `OPENALEX` solo se nessun test la usa: `tests/test_openalex_chiave.py` la nomina. Lasciala dov'è.

- [ ] **Step 7: Esegui tutta la suite**

Esegui: `python -m pytest -q`
Atteso: i test di `test_sources.py`, `test_keywords.py` e `test_openalex_chiave.py` passano ancora; falliscono solo quelli che toccano i campi nuovi di `Work` (Task 3).

- [ ] **Step 8: Commit**

```bash
git add ricerca/openalex_api.py ricerca/sources/openalex.py ricerca/keywords.py tests/test_openalex_api.py
git commit -m "refactor: una sola porta verso OpenAlex, con il costo contato"
```

---

### Task 3: Record arricchito

**Files:**
- Modify: `ricerca/models.py:44-90` (campi di `Work`), `ricerca/dedup.py:44-55`, `ricerca/export.py:13-32`
- Test: `tests/test_record_openalex.py`, `tests/test_dedup.py`

**Interfaces:**
- Consumes: `sources.openalex.work_da` (Task 2).
- Produces: `Work.openalex_id: str`, `Work.ritirato: bool`, `Work.citazioni: int | None`, `Work.molto_citato: bool`, `Work.pdf_archivio: str`; colonne di export `citazioni` e `ritirato`.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `tests/test_record_openalex.py`:

```python
import httpx
import respx

from ricerca import sources
from ricerca.config import Config

RISPOSTA = {"meta": {"cost_usd": 0.001}, "results": [{
    "id": "https://openalex.org/W42",
    "title": "Un articolo ritirato",
    "publication_year": 2024,
    "authorships": [],
    "primary_location": {},
    "abstract_inverted_index": {"Un": [0], "abstract": [1], "vero": [2]},
    "is_retracted": True,
    "cited_by_count": 137,
    "citation_normalized_percentile": {"is_in_top_10_percent": True},
    "has_content": {"pdf": True},
    "content_urls": {"pdf": "https://content.openalex.org/works/W42.pdf"},
}]}


@respx.mock
async def test_il_record_porta_i_campi_nuovi():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["openalex"].search(client, "q", 5, Config())
    work = works[0]
    assert work.openalex_id == "W42"
    assert work.abstract == "Un abstract vero"
    assert work.ritirato is True
    assert work.citazioni == 137
    assert work.molto_citato is True
    assert work.pdf_archivio == "https://content.openalex.org/works/W42.pdf"


@respx.mock
async def test_un_record_senza_i_campi_nuovi_non_esplode():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"meta": {}, "results": [{
            "id": "https://openalex.org/W1", "title": "Scarno",
            "authorships": [], "primary_location": {},
        }]})
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["openalex"].search(client, "q", 5, Config())
    assert works[0].abstract is None
    assert works[0].ritirato is False
    assert works[0].citazioni is None
    assert works[0].pdf_archivio == ""
```

E in `tests/test_dedup.py`:

```python
def test_la_fusione_tiene_i_campi_di_openalex():
    from ricerca.dedup import merge
    from ricerca.models import Work

    da_crossref = Work(title="Stesso lavoro", doi="10.1/x", sources=["crossref"])
    da_openalex = Work(
        title="Stesso lavoro", doi="10.1/x", sources=["openalex"],
        openalex_id="W9", citazioni=12, ritirato=True, molto_citato=True,
        pdf_archivio="https://content.openalex.org/works/W9.pdf",
    )
    unito = merge([da_crossref, da_openalex])[0]
    assert unito.openalex_id == "W9"
    assert unito.citazioni == 12
    assert unito.ritirato is True
    assert unito.molto_citato is True
    assert unito.pdf_archivio.endswith("W9.pdf")
```

- [ ] **Step 2: Esegui i test e verifica che falliscano**

Esegui: `python -m pytest tests/test_record_openalex.py tests/test_dedup.py -v`
Atteso: FAIL con `TypeError: Work.__init__() got an unexpected keyword argument 'openalex_id'`.

- [ ] **Step 3: Aggiungi i campi a `Work` in `ricerca/models.py`**

Dopo `sources: list[str] = field(default_factory=list)` (riga 61) inserisci:

```python
    # Quel che sa OpenAlex e le altre fonti non dicono: serve alle citazioni,
    # allo screening e all'ultimo tentativo di scaricare il PDF.
    openalex_id: str = ""
    ritirato: bool = False
    citazioni: int | None = None
    molto_citato: bool = False      # primo dieci per cento del suo campo e anno
    pdf_archivio: str = ""          # copia nell'archivio OpenAlex, a pagamento
```

- [ ] **Step 4: Estendi la fusione in `ricerca/dedup.py`**

La riga 45 diventa:

```python
    for campo in ("doi", "year", "venue", "url", "abstract", "oa_url", "openalex_id", "pdf_archivio", "citazioni"):
```

e subito dopo il ciclo, prima di `if len(work.authors) > len(kept.authors):`:

```python
    # Un ritiro visto da una fonte sola vale per il record intero.
    kept.ritirato = kept.ritirato or work.ritirato
    kept.molto_citato = kept.molto_citato or work.molto_citato
```

- [ ] **Step 5: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_record_openalex.py tests/test_dedup.py -v`
Atteso: PASS.

- [ ] **Step 6: Aggiungi le colonne agli export**

In `ricerca/export.py`, `CAMPI` (riga 13) diventa:

```python
CAMPI = (
    "anno", "titolo", "autori", "sede", "doi", "url", "abstract", "fonti", "pdf",
    "citazioni", "ritirato", "decisione", "motivo",
)
```

e `_ATTRIBUTI` guadagna due voci:

```python
    "citazioni": "citazioni",
    "ritirato": "ritirato",
```

`CAMPI_PREDEFINITI` non cambia: le colonne nuove si spuntano a mano.

- [ ] **Step 7: Scrivi il test dell'export e verificalo**

In `tests/test_export.py`:

```python
def test_il_csv_esporta_citazioni_e_ritiro():
    from ricerca.export import to_csv
    from ricerca.models import Work

    riga = to_csv([Work(title="X", citazioni=7, ritirato=True)], ["titolo", "citazioni", "ritirato"])
    assert "7" in riga
    assert "True" in riga or "true" in riga.lower()
```

Esegui: `python -m pytest tests/test_export.py -v`
Atteso: PASS. Se `to_csv` ha una firma diversa da `(works, campi)`, adeguala leggendo `ricerca/export.py`.

- [ ] **Step 8: Mostra ritiro e citazioni nella scheda**

In `ricerca/templates/partials/scheda.html`, sotto il titolo del record:

```html
{% if work.ritirato %}<p class="avviso-forte">{{ t.record_ritirato }}</p>{% endif %}
{% if work.citazioni is not none %}
  <p class="meta">{{ t.record_citazioni }}: {{ work.citazioni }}{% if work.molto_citato %} · {{ t.record_top10 }}{% endif %}</p>
{% endif %}
```

Chiavi da aggiungere in `ricerca/i18n.py`, in **entrambe** le lingue:

| chiave | it | en |
|---|---|---|
| `record_ritirato` | Articolo ritirato: non va incluso senza dirlo. | Retracted article: do not include it silently. |
| `record_citazioni` | Citazioni | Citations |
| `record_top10` | fra il 10% più citato del suo campo | in the top 10% most cited of its field |

- [ ] **Step 9: Esegui tutta la suite**

Esegui: `python -m pytest -q`
Atteso: PASS su tutto.

- [ ] **Step 10: Commit**

```bash
git add ricerca/models.py ricerca/dedup.py ricerca/export.py ricerca/i18n.py ricerca/templates/partials/scheda.html tests/
git commit -m "feat: il record OpenAlex porta abstract, ritiro e citazioni"
```

---

### Task 4: Filtri veri

**Files:**
- Modify: `ricerca/models.py:19-32` (`Filtri`), `ricerca/sources/openalex.py` (funzione `filtro`), `ricerca/strategy.py:81-105`, `ricerca/app.py:322-344` e `345-372`, `ricerca/templates/partials/strategia.html`, `ricerca/i18n.py`
- Test: `tests/test_filtri.py`

**Interfaces:**
- Consumes: `sources.openalex.filtro` (Task 2).
- Produces: `Filtri.lingua: str`, `Filtri.escludi_ritirati: bool`, `Filtri.solo_oa: bool`, `Filtri.con_pdf: bool`; `strategy_from_form(..., lingua="", escludi_ritirati=False, solo_oa=False, con_pdf=False)`.

- [ ] **Step 1: Scrivi il test che fallisce**

In `tests/test_filtri.py`:

```python
from ricerca.models import Filtri
from ricerca.sources.openalex import filtro


def test_i_filtri_nuovi_entrano_nella_stringa():
    reso = filtro("ai literacy", Filtri(
        lingua="en", escludi_ritirati=True, solo_oa=True, con_pdf=True
    ))
    assert "language:en" in reso
    assert "is_retracted:false" in reso
    assert "is_oa:true" in reso
    assert "has_content.pdf:true" in reso


def test_senza_filtri_la_stringa_resta_quella_di_prima():
    assert filtro("ai literacy", Filtri()) == "title_and_abstract.search:ai literacy"


def test_i_filtri_si_leggono_dal_modulo():
    from ricerca.strategy import strategy_from_form

    strategy = strategy_from_form(
        ["Blocco"], ["ai"], lingua="it", escludi_ritirati=True, solo_oa=True, con_pdf=False
    )
    assert strategy.filtri.lingua == "it"
    assert strategy.filtri.escludi_ritirati is True
    assert strategy.filtri.solo_oa is True
    assert strategy.filtri.con_pdf is False
    assert strategy.filtri.attivi() is True


def test_una_lingua_inventata_si_ignora():
    from ricerca.strategy import strategy_from_form

    assert strategy_from_form(["B"], ["ai"], lingua="klingon").filtri.lingua == ""
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Esegui: `python -m pytest tests/test_filtri.py -v`
Atteso: FAIL con `TypeError: Filtri.__init__() got an unexpected keyword argument 'lingua'`.

- [ ] **Step 3: Estendi `Filtri` in `ricerca/models.py`**

```python
@dataclass
class Filtri:
    """Vincoli che valgono per tutte le fonti, ognuna con la sua sintassi.

    Gli ultimi quattro li applica solo OpenAlex: le altre banche dati non
    espongono gli stessi campi, e l'interfaccia deve dirlo — un filtro
    ignorato in silenzio falsa il conteggio di una revisione.
    """

    anno_da: int | None = None
    anno_a: int | None = None
    solo_articoli: bool = False
    lingua: str = ""
    escludi_ritirati: bool = False
    solo_oa: bool = False
    con_pdf: bool = False

    def attivi(self) -> bool:
        return bool(
            self.anno_da or self.anno_a or self.solo_articoli
            or self.lingua or self.escludi_ritirati or self.solo_oa or self.con_pdf
        )
```

- [ ] **Step 4: Applica i filtri in `ricerca/sources/openalex.py`**

Dentro `filtro`, dopo il blocco `solo_articoli`:

```python
    if filtri and filtri.lingua:
        pezzi.append(f"language:{filtri.lingua}")
    if filtri and filtri.escludi_ritirati:
        pezzi.append("is_retracted:false")
    if filtri and filtri.solo_oa:
        pezzi.append("is_oa:true")
    if filtri and filtri.con_pdf:
        pezzi.append("has_content.pdf:true")
```

- [ ] **Step 5: Leggi i filtri dal modulo in `ricerca/strategy.py`**

`strategy_from_form` guadagna quattro parametri e una lista di lingue ammesse:

```python
# Le lingue che l'interfaccia offre: OpenAlex ne conosce molte di più, ma un
# codice inventato produce zero risultati senza spiegare perché.
LINGUE = ("en", "it", "es", "fr", "de", "pt")


def strategy_from_form(
    labels: list[str],
    term_lines: list[str],
    mesh: str = "",
    anno_da: str = "",
    anno_a: str = "",
    solo_articoli: bool = False,
    lingua: str = "",
    escludi_ritirati: bool = False,
    solo_oa: bool = False,
    con_pdf: bool = False,
) -> Strategy:
```

e nel `Filtri(...)` in coda:

```python
        filtri=Filtri(
            anno_da=_anno(anno_da),
            anno_a=_anno(anno_a),
            solo_articoli=bool(solo_articoli),
            lingua=lingua if lingua in LINGUE else "",
            escludi_ritirati=bool(escludi_ritirati),
            solo_oa=bool(solo_oa),
            con_pdf=bool(con_pdf),
        ),
```

- [ ] **Step 6: Passa i campi dalle rotte in `ricerca/app.py`**

Sia in `query` (riga 322) sia in `cerca` (riga 345) aggiungi i parametri dopo `solo_articoli`:

```python
    lingua: str = Form(default=""),
    escludi_ritirati: bool = Form(default=False),
    solo_oa: bool = Form(default=False),
    con_pdf: bool = Form(default=False),
```

e nella chiamata a `strategy_from_form`:

```python
    strategy = strategy_from_form(
        label, terms, mesh, anno_da, anno_a, solo_articoli,
        lingua, escludi_ritirati, solo_oa, con_pdf,
    )
```

- [ ] **Step 7: Metti i campi nel modulo**

In `ricerca/templates/partials/strategia.html`, accanto ai filtri esistenti (anno, solo articoli):

```html
<fieldset class="filtri-openalex">
  <legend>{{ t.filtri_openalex }}</legend>
  <label>{{ t.filtro_lingua }}
    <select name="lingua">
      <option value="">{{ t.filtro_lingua_tutte }}</option>
      {% for codice in lingue %}<option value="{{ codice }}">{{ codice }}</option>{% endfor %}
    </select>
  </label>
  <label><input type="checkbox" name="escludi_ritirati" value="1"> {{ t.filtro_ritirati }}</label>
  <label><input type="checkbox" name="solo_oa" value="1"> {{ t.filtro_oa }}</label>
  <label><input type="checkbox" name="con_pdf" value="1"> {{ t.filtro_pdf }}</label>
</fieldset>
```

`lingue` va passata dal contesto: in `ricerca/app.py`, dentro `base_context`, aggiungi `"lingue": strategy_module.LINGUE` importando `from .strategy import LINGUE`. Se `base_context` non è il posto giusto, passala nella sola `suggerimenti`.

Chiavi i18n nuove:

| chiave | it | en |
|---|---|---|
| `filtri_openalex` | Filtri OpenAlex (le altre banche dati li ignorano) | OpenAlex filters (other databases ignore them) |
| `filtro_lingua` | Lingua | Language |
| `filtro_lingua_tutte` | tutte | any |
| `filtro_ritirati` | Escludi gli articoli ritirati | Exclude retracted articles |
| `filtro_oa` | Solo ad accesso aperto | Open access only |
| `filtro_pdf` | Solo con il PDF nell'archivio OpenAlex | Only with a PDF in the OpenAlex archive |

- [ ] **Step 8: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_filtri.py tests/test_i18n.py -q`
Atteso: PASS.

- [ ] **Step 9: Commit**

```bash
git add ricerca/models.py ricerca/sources/openalex.py ricerca/strategy.py ricerca/app.py ricerca/i18n.py ricerca/templates/partials/strategia.html tests/test_filtri.py
git commit -m "feat: filtri per lingua, ritiro, accesso aperto e PDF"
```

---

### Task 5: OQL nel protocollo, credito a schermo

**Files:**
- Modify: `ricerca/search.py:96-130` (raccolta dell'OQL), `ricerca/models.py` (`SourceResult.oql`), `ricerca/history.py:52-70`, `ricerca/export.py:181-250`, `ricerca/app.py` (contesto delle impostazioni), `ricerca/templates/impostazioni.html`, `ricerca/i18n.py`
- Create: `ricerca/templates/partials/credito.html`
- Test: `tests/test_oql.py`, `tests/test_credito.py`

**Interfaces:**
- Consumes: `openalex_api.oql` (Task 2), `costo.speso`, `costo.resta`, `costo.budget` (Task 1).
- Produces: `SourceResult.oql: str`; la voce di cronologia porta `fonti[].oql`; `export.protocollo` e `export.protocollo_testo` stampano la riga OQL.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `tests/test_oql.py`:

```python
import httpx
import respx

from ricerca import search
from ricerca.config import Config
from ricerca.models import Block, Strategy

OQL = "works where title/abstract has (ai literacy)"


@respx.mock
async def test_l_oql_arriva_nel_risultato_della_fonte():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={
            "meta": {"cost_usd": 0.001, "x_query": {"oql": OQL}}, "results": [],
        })
    )
    strategy = Strategy(blocks=[Block("B", ["ai literacy"])])
    results, _ = await search.run(strategy, ["openalex"], 5, Config())
    assert results[0].oql == OQL


def test_il_protocollo_stampa_l_oql():
    from ricerca.export import protocollo, protocollo_testo

    voce = {
        "topic": "ai literacy", "quando": "2026-08-20T10:00:00", "blocchi": [],
        "fonti": [{"id": "openalex", "etichetta": "OpenAlex", "query": "(x)", "trovati": 3, "oql": OQL}],
    }
    assert OQL in protocollo(voce, {})
    assert OQL in protocollo_testo(voce, {})


def test_una_fonte_senza_oql_non_stampa_la_riga():
    from ricerca.export import protocollo

    voce = {
        "topic": "x", "quando": "2026-08-20T10:00:00", "blocchi": [],
        "fonti": [{"id": "pubmed", "etichetta": "PubMed", "query": "(x)", "trovati": 1}],
    }
    assert "OQL" not in protocollo(voce, {})
```

Crea `tests/test_credito.py`:

```python
from fastapi.testclient import TestClient

from ricerca import costo
from ricerca import config as config_module
from ricerca.app import app
from ricerca.config import Config

client = TestClient(app)


def test_le_impostazioni_mostrano_quanto_resta():
    config_module.save(Config(configurato="1", openalex_api_key="k"))
    costo.aggiungi(0.25)
    pagina = client.get("/impostazioni").text
    assert "0.25" in pagina
    assert "0.75" in pagina


def test_senza_chiave_il_budget_e_quello_stretto():
    config_module.save(Config(configurato="1"))
    pagina = client.get("/impostazioni").text
    assert "0.10" in pagina
```

- [ ] **Step 2: Esegui i test e verifica che falliscano**

Esegui: `python -m pytest tests/test_oql.py tests/test_credito.py -v`
Atteso: FAIL — `SourceResult` non ha `oql`, e la pagina delle impostazioni non nomina il credito.

- [ ] **Step 3: Porta l'OQL dalla fonte al risultato**

In `ricerca/models.py`, dentro `SourceResult`, dopo `secondi: float = 0.0`:

```python
    # La stessa interrogazione riscritta da OpenAlex nel suo linguaggio: è la
    # strategia riproducibile da allegare a una revisione.
    oql: str = ""
```

In `ricerca/search.py`, dentro `_one`, subito **prima** del ciclo dei tentativi:

```python
    openalex_api.ULTIMA_OQL.set("")
```

e subito dopo `result.works = await source.search(...)`:

```python
            result.oql = openalex_api.ULTIMA_OQL.get("")
```

Aggiungi `from . import openalex_api` agli import di `ricerca/search.py`. Il valore viaggia nella variabile di contesto e non su un attributo della fonte perché nel registro le fonti sono istanze uniche: due ricerche avviate insieme si sovrascriverebbero il valore a vicenda. `_one` gira dentro un compito di `asyncio.gather`, che ne riceve una copia propria.

In `ricerca/search.py`, dentro `statistiche`, aggiungi alla riga del dizionario:

```python
                "oql": result.oql,
```

- [ ] **Step 4: Stampa l'OQL nel protocollo**

In `ricerca/export.py`, dentro `protocollo`, dopo il ciclo sulle fonti aggiungi:

```python
    oql = [f for f in voce.get("fonti", []) if f.get("oql")]
    if oql:
        righe += ["", "## Query OQL (OpenAlex)", ""]
        righe += [f"- **{f.get('etichetta', '')}**: `{f['oql']}`" for f in oql]
```

e dentro `protocollo_testo`, dopo il ciclo sulle fonti:

```python
    oql = [f for f in voce.get("fonti", []) if f.get("oql")]
    if oql:
        righe += ["", "QUERY OQL (OPENALEX)"]
        righe += [f"  {f.get('etichetta', '')}: {f['oql']}" for f in oql]
```

- [ ] **Step 5: Mostra il credito nelle impostazioni**

Crea `ricerca/templates/partials/credito.html`:

```html
<p class="credito">
  {{ t.credito_speso }}: <b>${{ "%.4f"|format(credito_speso) }}</b> ·
  {{ t.credito_resta }}: <b>${{ "%.2f"|format(credito_resta) }}</b>
  {{ t.credito_su }} ${{ "%.2f"|format(credito_budget) }}
  <small>{{ t.credito_nota }}</small>
</p>
```

In `ricerca/app.py`, nella rotta che rende `impostazioni.html`, aggiungi al contesto:

```python
        credito_speso=costo.speso(),
        credito_resta=costo.resta(config),
        credito_budget=costo.budget(config),
```

importando `costo` dalla riga degli import di pacchetto. In `ricerca/templates/impostazioni.html`, vicino al campo della chiave OpenAlex:

```html
{% include "partials/credito.html" %}
```

Chiavi i18n:

| chiave | it | en |
|---|---|---|
| `credito_speso` | Credito OpenAlex speso oggi | OpenAlex credit spent today |
| `credito_resta` | resta | left |
| `credito_su` | su | of |
| `credito_nota` | Il conto si azzera ogni giorno. Una ricerca costa $0.001, un filtro $0.0001, un PDF dall'archivio $0.01. | The budget resets daily. A search costs $0.001, a filter $0.0001, an archive PDF $0.01. |

- [ ] **Step 6: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_oql.py tests/test_credito.py tests/test_i18n.py -q`
Atteso: PASS.

- [ ] **Step 7: Esegui tutta la suite**

Esegui: `python -m pytest -q`
Atteso: PASS.

- [ ] **Step 8: Commit**

```bash
git add ricerca/models.py ricerca/search.py ricerca/export.py ricerca/app.py ricerca/i18n.py ricerca/templates/ tests/test_oql.py tests/test_credito.py
git commit -m "feat: la query OQL nel protocollo e il credito speso a schermo"
```

---

# Fase 2 — PDF dall'archivio

### Task 6: L'archivio OpenAlex come ultimo tentativo

**Files:**
- Modify: `ricerca/openalex_api.py` (funzione `contenuto_pdf`), `ricerca/pdf.py:150-200` (`scarica`), `ricerca/config.py:29-45`, `ricerca/templates/impostazioni.html`, `ricerca/app.py` (rotta `/impostazioni`), `ricerca/i18n.py`
- Test: `tests/test_pdf_archivio.py`

**Interfaces:**
- Consumes: `Work.pdf_archivio`, `Work.openalex_id` (Task 3); `costo.COSTO_PDF` (Task 1).
- Produces: `openalex_api.contenuto_pdf(work_id: str, config: Config, client: httpx.AsyncClient) -> bytes`; `Config.openalex_contenuti: str` (`"1"` acceso, `""` spento).

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `tests/test_pdf_archivio.py`:

```python
import httpx
import pytest
import respx

from ricerca import costo, pdf
from ricerca import config as config_module
from ricerca.config import Config
from ricerca.models import Work

PDF_FINTO = b"%PDF-1.4 finto"


def lavoro() -> Work:
    return Work(
        title="Un articolo", year=2024, doi="10.1/x",
        oa_url="https://editore/rotto.pdf",
        openalex_id="W42",
        pdf_archivio="https://content.openalex.org/works/W42.pdf",
    )


@respx.mock
async def test_l_archivio_si_prova_solo_dopo_gli_altri():
    config_module.save(Config(openalex_api_key="k", openalex_contenuti="1"))
    respx.get("https://editore/rotto.pdf").mock(return_value=httpx.Response(404))
    archivio = respx.get(url__startswith="https://content.openalex.org/works/W42.pdf").mock(
        return_value=httpx.Response(200, content=PDF_FINTO)
    )
    async with httpx.AsyncClient() as client:
        percorso = await pdf.scarica(lavoro(), client)
    assert percorso.read_bytes() == PDF_FINTO
    assert "api_key=k" in str(archivio.calls[0].request.url)
    assert costo.speso() == costo.COSTO_PDF


@respx.mock
async def test_se_il_collegamento_aperto_funziona_l_archivio_non_si_tocca():
    config_module.save(Config(openalex_api_key="k", openalex_contenuti="1"))
    respx.get("https://editore/rotto.pdf").mock(
        return_value=httpx.Response(200, content=PDF_FINTO)
    )
    archivio = respx.get(url__startswith="https://content.openalex.org").mock(
        return_value=httpx.Response(200, content=PDF_FINTO)
    )
    async with httpx.AsyncClient() as client:
        await pdf.scarica(lavoro(), client)
    assert not archivio.called
    assert costo.speso() == 0.0


@respx.mock
async def test_spento_di_suo_non_si_paga_niente():
    config_module.save(Config(openalex_api_key="k"))       # opzione non accesa
    respx.get("https://editore/rotto.pdf").mock(return_value=httpx.Response(404))
    archivio = respx.get(url__startswith="https://content.openalex.org").mock(
        return_value=httpx.Response(200, content=PDF_FINTO)
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await pdf.scarica(lavoro(), client)
    assert not archivio.called


@respx.mock
async def test_senza_chiave_l_archivio_non_si_prova():
    config_module.save(Config(openalex_contenuti="1"))
    respx.get("https://editore/rotto.pdf").mock(return_value=httpx.Response(404))
    archivio = respx.get(url__startswith="https://content.openalex.org").mock(
        return_value=httpx.Response(401, json={"error": "API key required"})
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await pdf.scarica(lavoro(), client)
    assert not archivio.called
```

- [ ] **Step 2: Esegui i test e verifica che falliscano**

Esegui: `python -m pytest tests/test_pdf_archivio.py -v`
Atteso: FAIL con `TypeError: Config.__init__() got an unexpected keyword argument 'openalex_contenuti'`.

- [ ] **Step 3: Aggiungi l'opzione a `ricerca/config.py`**

Dopo `openalex_api_key: str = ""`:

```python
    # L'archivio dei PDF di OpenAlex costa $0.01 a file: si accende a mano.
    openalex_contenuti: str = ""
```

- [ ] **Step 4: Scrivi `contenuto_pdf` in `ricerca/openalex_api.py`**

```python
async def contenuto_pdf(work_id: str, config: Config, client: httpx.AsyncClient) -> bytes:
    """Il PDF dall'archivio di OpenAlex: $0.01 a file, chiave obbligatoria.

    Il corpo non dichiara la spesa come fa l'API dei metadati, quindi il
    costo si annota qui a listino.
    """

    if not config.openalex_api_key:
        raise ValueError("l'archivio OpenAlex vuole la chiave")
    risposta = await client.get(
        f"{CONTENUTI}/works/{work_id}.pdf",
        params={"api_key": config.openalex_api_key},
        timeout=120,
        follow_redirects=True,
    )
    risposta.raise_for_status()
    costo.aggiungi(costo.COSTO_PDF)
    return risposta.content
```

- [ ] **Step 5: Usa l'archivio come ultimo tentativo in `ricerca/pdf.py`**

Dentro `scarica`, subito prima di `if contenuto is None: raise ValueError(...)`:

```python
    if contenuto is None:
        contenuto = await _dall_archivio(work, motivi)
```

e in fondo al modulo:

```python
async def _dall_archivio(work: Work, motivi: list[str]) -> bytes | None:
    """L'ultima strada: la copia nell'archivio di OpenAlex, che si paga.

    Si prova solo quando i collegamenti aperti hanno fallito tutti, l'opzione
    è accesa e la chiave c'è: nessuna spesa parte da sola.
    """

    from . import openalex_api

    config = config_module.load()
    identificativo = work.openalex_id or openalex_api.id_breve(work.pdf_archivio).removesuffix(".pdf")
    if not (config.openalex_contenuti and config.openalex_api_key and identificativo):
        return None
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            contenuto = await openalex_api.contenuto_pdf(identificativo, config, client)
        except (httpx.HTTPError, ValueError) as exc:
            motivi.append(f"archivio: {type(exc).__name__}")
            return None
    if not contenuto.startswith(b"%PDF"):
        motivi.append("archivio: non è un PDF")
        return None
    annota(
        strings(config.lang)["log_pdf_archivio"],
        f"{identificativo} · ${costo.COSTO_PDF:.2f}",
    )
    return contenuto
```

Aggiungi in cima al file `from . import costo`.

Il client si apre qui invece di riusare quello ricevuto da `scarica`: quello può avere la cache montata, e un file da $0.01 e decine di megabyte non va nella cache SQLite delle risposte. `respx` intercetta tutti i client httpx finché il mock è attivo, quindi i test vedono lo stesso la chiamata.

- [ ] **Step 6: Metti l'interruttore nelle impostazioni**

In `ricerca/templates/impostazioni.html`, sotto la chiave OpenAlex:

```html
<label class="interruttore">
  <input type="checkbox" name="openalex_contenuti" value="1"
         {% if config.openalex_contenuti %}checked{% endif %}>
  {{ t.archivio_pdf }}
</label>
<small>{{ t.archivio_pdf_nota }}</small>
```

Nella rotta `POST /impostazioni` di `ricerca/app.py`, accetta `openalex_contenuti: str = Form(default="")` e salvalo nella `Config`.

Chiavi i18n:

| chiave | it | en |
|---|---|---|
| `archivio_pdf` | Scarica i PDF dall'archivio OpenAlex quando tutto il resto fallisce | Download PDFs from the OpenAlex archive when everything else fails |
| `archivio_pdf_nota` | Costa $0.01 a file e richiede la chiave. Il copyright resta quello originale: OpenAlex non concede diritti in più. | Costs $0.01 per file and needs the key. Copyright stays with the original: OpenAlex grants no extra rights. |
| `log_pdf_archivio` | PDF preso dall'archivio OpenAlex | PDF taken from the OpenAlex archive |

- [ ] **Step 7: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_pdf_archivio.py tests/test_pdf.py tests/test_pdf_articoli.py tests/test_i18n.py -q`
Atteso: PASS.

- [ ] **Step 8: Commit**

```bash
git add ricerca/openalex_api.py ricerca/pdf.py ricerca/config.py ricerca/app.py ricerca/i18n.py ricerca/templates/impostazioni.html tests/test_pdf_archivio.py
git commit -m "feat: l'archivio OpenAlex come ultima strada verso il PDF"
```

---

# Fase 3 — snowballing

### Task 7: Il modulo delle citazioni

**Files:**
- Create: `ricerca/citazioni.py`
- Test: `tests/test_citazioni.py`

**Interfaces:**
- Consumes: `openalex_api.chiama`, `openalex_api.id_breve` (Task 2); `sources.openalex.work_da`, `sources.openalex.SELECT` (Task 2); `Work.openalex_id` (Task 3).
- Produces: `citazioni.VERSI: tuple[str, ...]`, `citazioni.cerca(work: Work, verso: str, config: Config, client: httpx.AsyncClient, limite: int = 50) -> list[Work]`, `citazioni.per_id(ids: list[str], config: Config, client: httpx.AsyncClient) -> list[Work]`.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `tests/test_citazioni.py`:

```python
import httpx
import pytest
import respx

from ricerca import citazioni
from ricerca.config import Config
from ricerca.models import Work


def lavoro() -> Work:
    return Work(title="Il seme", openalex_id="W1", sources=["openalex"])


def risultato(*ids):
    return {"meta": {"cost_usd": 0.0001}, "results": [
        {"id": f"https://openalex.org/{i}", "title": f"Trovato {i}",
         "authorships": [], "primary_location": {}} for i in ids
    ]}


@respx.mock
async def test_avanti_chiede_chi_lo_cita():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=risultato("W9"))
    )
    async with httpx.AsyncClient() as client:
        trovati = await citazioni.cerca(lavoro(), "avanti", Config(), client)
    assert "cites%3AW1" in str(rotta.calls[0].request.url)
    assert trovati[0].openalex_id == "W9"
    assert trovati[0].sources == ["openalex"]


@respx.mock
async def test_indietro_legge_la_bibliografia_e_poi_i_record():
    respx.get(url__startswith="https://api.openalex.org/works/W1").mock(
        return_value=httpx.Response(200, json={
            "meta": {"cost_usd": 0.0},
            "id": "https://openalex.org/W1",
            "referenced_works": ["https://openalex.org/W7", "https://openalex.org/W8"],
        })
    )
    respx.get(url__startswith="https://api.openalex.org/works?").mock(
        return_value=httpx.Response(200, json=risultato("W7", "W8"))
    )
    async with httpx.AsyncClient() as client:
        trovati = await citazioni.cerca(lavoro(), "indietro", Config(), client)
    assert [w.openalex_id for w in trovati] == ["W7", "W8"]


@respx.mock
async def test_di_lato_usa_i_lavori_vicini():
    respx.get(url__startswith="https://api.openalex.org/works/W1").mock(
        return_value=httpx.Response(200, json={
            "meta": {}, "id": "https://openalex.org/W1",
            "related_works": ["https://openalex.org/W5"],
        })
    )
    respx.get(url__startswith="https://api.openalex.org/works?").mock(
        return_value=httpx.Response(200, json=risultato("W5"))
    )
    async with httpx.AsyncClient() as client:
        trovati = await citazioni.cerca(lavoro(), "lato", Config(), client)
    assert trovati[0].openalex_id == "W5"


@respx.mock
async def test_i_blocchi_sono_da_cento():
    ids = [f"W{n}" for n in range(1, 151)]
    rotta = respx.get(url__startswith="https://api.openalex.org/works?").mock(
        return_value=httpx.Response(200, json=risultato("W1"))
    )
    async with httpx.AsyncClient() as client:
        await citazioni.per_id(ids, Config(), client)
    assert len(rotta.calls) == 2       # cento e cinquanta


async def test_un_record_senza_identificativo_lo_dice():
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await citazioni.cerca(Work(title="Da Crossref"), "avanti", Config(), client)


async def test_un_verso_inventato_lo_dice():
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await citazioni.cerca(lavoro(), "diagonale", Config(), client)
```

Nota: l'ordine dei mock conta. `respx` prende il primo modello che combacia, quindi va registrato prima `.../works/W1` (la scheda singola) e poi `.../works?` (l'elenco filtrato).

- [ ] **Step 2: Esegui i test e verifica che falliscano**

Esegui: `python -m pytest tests/test_citazioni.py -v`
Atteso: FAIL con `ModuleNotFoundError: No module named 'ricerca.citazioni'`.

- [ ] **Step 3: Scrivi `ricerca/citazioni.py`**

```python
"""Snowballing: da un articolo trovato agli articoli che gli stanno intorno.

Tre direzioni, tutte da OpenAlex:
- **indietro**, la bibliografia dell'articolo (`referenced_works`);
- **avanti**, chi lo cita (`filter=cites:`);
- **di lato**, i lavori che OpenAlex considera vicini (`related_works`).

La scheda del singolo lavoro non costa nulla; i record veri si prendono a
blocchi di cento, il massimo di valori in OR che un filtro accetta.
"""

from __future__ import annotations

import httpx

from . import openalex_api
from .config import Config
from .models import Work
from .sources.openalex import SELECT, work_da

VERSI = ("indietro", "avanti", "lato")
BLOCCO = 100          # valori in OR ammessi da un filtro


async def cerca(
    work: Work,
    verso: str,
    config: Config,
    client: httpx.AsyncClient,
    limite: int = 50,
) -> list[Work]:
    if verso not in VERSI:
        raise ValueError(f"verso sconosciuto: {verso}")
    identificativo = work.openalex_id or openalex_api.id_breve(work.url)
    if not identificativo.startswith("W"):
        raise ValueError("questo record non ha un identificativo OpenAlex")

    if verso == "avanti":
        corpo = await openalex_api.chiama(
            client,
            "/works",
            config,
            filter=f"cites:{identificativo}",
            per_page=str(min(limite, 100)),
            select=SELECT,
            sort="cited_by_count:desc",
        )
        return [work_da(item) for item in corpo.get("results", [])]

    campo = "referenced_works" if verso == "indietro" else "related_works"
    scheda = await openalex_api.chiama(
        client, f"/works/{identificativo}", config, select=f"id,{campo}"
    )
    ids = [openalex_api.id_breve(u) for u in (scheda.get(campo) or [])]
    return await per_id(ids[:limite], config, client)


async def per_id(ids: list[str], config: Config, client: httpx.AsyncClient) -> list[Work]:
    """I record di una lista di identificativi, a blocchi di cento."""

    trovati: list[Work] = []
    for inizio in range(0, len(ids), BLOCCO):
        gruppo = [i for i in ids[inizio : inizio + BLOCCO] if i]
        if not gruppo:
            continue
        corpo = await openalex_api.chiama(
            client,
            "/works",
            config,
            filter="openalex:" + "|".join(gruppo),
            per_page=str(BLOCCO),
            select=SELECT,
        )
        trovati.extend(work_da(item) for item in corpo.get("results", []))
    return trovati
```

- [ ] **Step 4: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_citazioni.py -v`
Atteso: PASS, sei test.

- [ ] **Step 5: Scrivi il test a contratto contro l'API vera**

Crea `tests/contratto/test_citazioni_rete.py`:

```python
import httpx
import pytest

from ricerca import citazioni
from ricerca.config import Config
from ricerca.models import Work

pytestmark = pytest.mark.rete


async def test_le_tre_direzioni_rispondono_davvero():
    seme = Work(title="Semantic Scholar", openalex_id="W2741809807")
    async with httpx.AsyncClient() as client:
        for verso in citazioni.VERSI:
            trovati = await citazioni.cerca(seme, verso, Config(), client, limite=5)
            assert trovati, f"nessun risultato per {verso}"
```

Esegui: `python -m pytest tests/contratto/test_citazioni_rete.py -m rete -v`
Atteso: PASS (spende meno di $0.001). Se fallisce per budget esaurito, riprova domani: non è un difetto del codice.

- [ ] **Step 6: Commit**

```bash
git add ricerca/citazioni.py tests/test_citazioni.py tests/contratto/test_citazioni_rete.py
git commit -m "feat: citazioni avanti, indietro e di lato da OpenAlex"
```

---

### Task 8: Le citazioni nella scheda

**Files:**
- Create: `ricerca/templates/partials/citazioni.html`
- Modify: `ricerca/app.py` (due rotte nuove), `ricerca/history.py` (funzione `aggiungi`), `ricerca/templates/partials/scheda.html`, `ricerca/i18n.py`
- Test: `tests/test_citazioni_scheda.py`, `tests/test_history.py`

**Interfaces:**
- Consumes: `citazioni.cerca`, `citazioni.VERSI` (Task 7).
- Produces: `history.aggiungi(id_voce: str, nuovi: list[Work], etichetta: str) -> int` (restituisce quanti record sono entrati davvero); rotte `GET /citazioni/{id_ricerca}/{indice}/{verso}` e `POST /citazioni/{id_ricerca}/{indice}/{verso}`.

- [ ] **Step 1: Scrivi il test di `history.aggiungi`**

In `tests/test_history.py`:

```python
def test_i_record_nuovi_vanno_in_coda_senza_duplicare():
    from ricerca import history
    from ricerca.models import Block, SourceResult, Strategy, Work

    strategy = Strategy(blocks=[Block("B", ["x"])])
    esistenti = [Work(title="Primo", doi="10.1/a"), Work(title="Secondo", doi="10.1/b")]
    id_voce = history.salva("topic", strategy, [SourceResult("openalex", "OpenAlex", "q")], esistenti)

    entrati = history.aggiungi(
        id_voce,
        [Work(title="Primo di nuovo", doi="10.1/a"), Work(title="Terzo", doi="10.1/c")],
        "citazioni",
    )
    record = history.record(id_voce)
    assert entrati == 1
    assert [w.title for w in record] == ["Primo", "Secondo", "Terzo"]
    assert record[2].sources == ["citazioni"]


def test_le_decisioni_gia_prese_restano_sul_record_giusto():
    from ricerca import history
    from ricerca.models import Block, SourceResult, Strategy, Work

    strategy = Strategy(blocks=[Block("B", ["x"])])
    id_voce = history.salva(
        "topic", strategy, [SourceResult("openalex", "OpenAlex", "q")],
        [Work(title="Primo", doi="10.1/a"), Work(title="Secondo", doi="10.1/b")],
    )
    history.decide(id_voce, 1, "incluso", "pertinente")
    history.aggiungi(id_voce, [Work(title="Terzo", doi="10.1/c")], "citazioni")
    record = history.record(id_voce)
    assert record[1].title == "Secondo"
    assert record[1].decisione == "incluso"
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Esegui: `python -m pytest tests/test_history.py -v`
Atteso: FAIL con `AttributeError: module 'ricerca.history' has no attribute 'aggiungi'`.

- [ ] **Step 3: Scrivi `history.aggiungi`**

In `ricerca/history.py`, dopo `salva`:

```python
def aggiungi(id_voce: str, nuovi: list[Work], etichetta: str) -> int:
    """Attacca record nuovi a una ricerca già fatta, in coda e senza doppioni.

    In coda perché le decisioni di screening sono indicizzate per posizione:
    inserire in mezzo le sposterebbe tutte sul record sbagliato. La
    provenienza sostituisce quella della fonte, così nel protocollo si vede
    che sono arrivati dallo snowballing e non dalla query.
    """

    from .dedup import _key

    voci = _leggi()
    for voce in voci:
        if voce.get("id") != id_voce:
            continue
        presenti = {_key(Work(**_campi(r))) for r in voce.get("record", [])}
        entrati = 0
        for work in nuovi:
            if _key(work) in presenti:
                continue
            presenti.add(_key(work))
            work.sources = [etichetta]
            voce.setdefault("record", []).append(asdict(work))
            entrati += 1
        voce["totale"] = len(voce.get("record", []))
        _scrivi(voci)
        return entrati
    return 0


def _campi(record: dict) -> dict:
    """Solo le chiavi che `Work` conosce: una cronologia vecchia può averne
    di più o di meno di quelle del programma di oggi."""

    ammessi = set(Work.__dataclass_fields__)
    return {k: v for k, v in record.items() if k in ammessi}
```

Se in `ricerca/history.py` la ricostruzione dei `Work` avviene già con una funzione simile (guarda `record()`), riusala invece di scrivere `_campi`.

- [ ] **Step 4: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_history.py -v`
Atteso: PASS.

- [ ] **Step 5: Scrivi il test delle rotte**

Crea `tests/test_citazioni_scheda.py`:

```python
import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import history
from ricerca.app import app
from ricerca.models import Block, SourceResult, Strategy, Work

client = TestClient(app)


def ricerca_salvata() -> str:
    return history.salva(
        "topic",
        Strategy(blocks=[Block("B", ["x"])]),
        [SourceResult("openalex", "OpenAlex", "q")],
        [Work(title="Il seme", openalex_id="W1", sources=["openalex"])],
    )


RISPOSTA = {"meta": {"cost_usd": 0.0001}, "results": [{
    "id": "https://openalex.org/W9", "title": "Chi mi cita",
    "publication_year": 2025, "authorships": [], "primary_location": {},
}]}


@respx.mock
def test_la_scheda_elenca_chi_cita():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    id_ricerca = ricerca_salvata()
    pagina = client.get(f"/citazioni/{id_ricerca}/0/avanti")
    assert pagina.status_code == 200
    assert "Chi mi cita" in pagina.text


@respx.mock
def test_i_record_scelti_entrano_nella_ricerca():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    id_ricerca = ricerca_salvata()
    risposta = client.post(f"/citazioni/{id_ricerca}/0/avanti", data={"scelti": ["W9"]})
    assert risposta.status_code == 200
    titoli = [w.title for w in history.record(id_ricerca)]
    assert titoli == ["Il seme", "Chi mi cita"]


def test_un_record_senza_identificativo_spiega_invece_di_rompersi():
    id_ricerca = history.salva(
        "topic", Strategy(blocks=[Block("B", ["x"])]),
        [SourceResult("crossref", "Crossref", "q")],
        [Work(title="Da Crossref", sources=["crossref"])],
    )
    pagina = client.get(f"/citazioni/{id_ricerca}/0/avanti")
    assert pagina.status_code == 200
    assert "OpenAlex" in pagina.text
```

- [ ] **Step 6: Esegui il test e verifica che fallisca**

Esegui: `python -m pytest tests/test_citazioni_scheda.py -v`
Atteso: FAIL con `404 Not Found` sulla rotta.

- [ ] **Step 7: Scrivi le rotte in `ricerca/app.py`**

```python
@app.get("/citazioni/{id_ricerca}/{indice}/{verso}", response_class=HTMLResponse)
async def citazioni_elenco(request: Request, id_ricerca: str, indice: int, verso: str):
    """I lavori intorno a questo: chi lo cita, chi cita lui, chi gli somiglia."""

    config = current_config()
    works = history.record(id_ricerca)
    if not works or indice >= len(works):
        return HTMLResponse("")
    t = i18n.strings(config.lang)
    trovati, problema = [], ""
    async with cache.client(
        headers={"User-Agent": search.USER_AGENT}, follow_redirects=True
    ) as http:
        try:
            trovati = await citazioni.cerca(works[indice], verso, config, http)
        except ValueError:
            problema = t["citazioni_senza_id"]
        except (httpx.HTTPError, OSError) as exc:
            problema = keywords.messaggio_api(exc.response) if isinstance(
                exc, httpx.HTTPStatusError
            ) else t["err_rete_fonte"]

    presenti = {(w.openalex_id or w.doi or w.title) for w in works}
    return templates.TemplateResponse(
        request,
        "partials/citazioni.html",
        base_context(
            config,
            id_ricerca=id_ricerca,
            indice=indice,
            verso=verso,
            trovati=[w for w in trovati if (w.openalex_id or w.doi or w.title) not in presenti],
            problema=problema,
        ),
    )


@app.post("/citazioni/{id_ricerca}/{indice}/{verso}", response_class=HTMLResponse)
async def citazioni_aggiungi(
    request: Request,
    id_ricerca: str,
    indice: int,
    verso: str,
    scelti: list[str] = Form(default=[]),
):
    """Porta nella ricerca i record spuntati, in coda e con la provenienza."""

    config = current_config()
    if not scelti:
        return HTMLResponse("")
    async with cache.client(
        headers={"User-Agent": search.USER_AGENT}, follow_redirects=True
    ) as http:
        nuovi = await citazioni.per_id(scelti, config, http)
    entrati = history.aggiungi(id_ricerca, nuovi, "citazioni")
    registro.annota(
        i18n.strings(config.lang)["log_citazioni_aggiunte"].format(quanti=entrati),
        f"{id_ricerca} · {verso}",
    )
    return _scheda(request, id_ricerca, indice)
```

Aggiungi `citazioni` alla riga di import di pacchetto in cima al file.

- [ ] **Step 8: Scrivi il partial**

Crea `ricerca/templates/partials/citazioni.html`:

```html
<div class="citazioni">
  {% if problema %}
    <p class="avviso">{{ problema }}</p>
  {% elif not trovati %}
    <p class="meta">{{ t.citazioni_nessuna }}</p>
  {% else %}
    <form hx-post="/citazioni/{{ id_ricerca }}/{{ indice }}/{{ verso }}" hx-target="closest .scheda">
      <ul class="elenco-citazioni">
        {% for work in trovati %}
          <li>
            <label>
              <input type="checkbox" name="scelti" value="{{ work.openalex_id }}">
              <b>{{ work.title }}</b>
              <small>{{ work.authors_short }}{% if work.year %} · {{ work.year }}{% endif %}
              {% if work.citazioni is not none %} · {{ work.citazioni }} {{ t.record_citazioni|lower }}{% endif %}</small>
            </label>
          </li>
        {% endfor %}
      </ul>
      <button type="submit">{{ t.citazioni_aggiungi }}</button>
    </form>
  {% endif %}
</div>
```

E in `ricerca/templates/partials/scheda.html`, tre bottoni che caricano l'elenco:

```html
<div class="azioni-citazioni">
  {% for verso, etichetta in [("indietro", t.citazioni_indietro), ("avanti", t.citazioni_avanti), ("lato", t.citazioni_lato)] %}
    <button hx-get="/citazioni/{{ id_ricerca }}/{{ indice }}/{{ verso }}"
            hx-target="#citazioni-{{ indice }}">{{ etichetta }}</button>
  {% endfor %}
</div>
<div id="citazioni-{{ indice }}"></div>
```

Chiavi i18n:

| chiave | it | en |
|---|---|---|
| `citazioni_indietro` | La sua bibliografia | Its bibliography |
| `citazioni_avanti` | Chi lo cita | Citing works |
| `citazioni_lato` | Lavori vicini | Related works |
| `citazioni_aggiungi` | Aggiungi alla ricerca | Add to the search |
| `citazioni_nessuna` | Nessun lavoro nuovo da questa parte. | Nothing new on this side. |
| `citazioni_senza_id` | Questo record non viene da OpenAlex: le citazioni partono solo dai record OpenAlex. | This record is not from OpenAlex: citation chasing starts from OpenAlex records only. |
| `log_citazioni_aggiunte` | {quanti} record aggiunti dalle citazioni | {quanti} records added from citation chasing |

- [ ] **Step 9: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_citazioni_scheda.py tests/test_scheda.py tests/test_i18n.py -q`
Atteso: PASS.

- [ ] **Step 10: Commit**

```bash
git add ricerca/app.py ricerca/history.py ricerca/i18n.py ricerca/templates/partials/ tests/
git commit -m "feat: snowballing dalla scheda, con i record scelti in coda alla ricerca"
```

---

# Fase 4 — esplorazione

### Task 9: Profilo del campo

**Files:**
- Create: `ricerca/faccette.py`, `ricerca/templates/partials/faccette.html`
- Modify: `ricerca/app.py` (rotta), `ricerca/history.py` (i filtri nella voce), `ricerca/export.py` (i filtri nel protocollo), `ricerca/templates/partials/risultati.html`, `ricerca/i18n.py`, `ricerca/static/` (poche righe di CSS per le barre)
- Test: `tests/test_faccette.py`

**Interfaces:**
- Consumes: `openalex_api.chiama` (Task 2), `sources.openalex.filtro` (Task 4).
- Produces: `faccette.CAMPI: tuple[tuple[str, str], ...]`, `faccette.profilo(query: str, filtri, config: Config, client: httpx.AsyncClient, quanti: int = 12) -> list[dict]`; la voce di cronologia porta `filtri` (il dizionario di `Filtri`), letto dalle faccette e stampato nel protocollo.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `tests/test_faccette.py`:

```python
import httpx
import respx

from ricerca import faccette
from ricerca.config import Config
from ricerca.models import Filtri


def gruppi(*coppie):
    return {"meta": {"cost_usd": 0.0001}, "group_by": [
        {"key": str(k), "key_display_name": str(k), "count": n} for k, n in coppie
    ]}


@respx.mock
async def test_il_profilo_raccoglie_tutti_i_campi():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=gruppi(("2024", 40), ("2023", 10)))
    )
    async with httpx.AsyncClient() as client:
        profilo = await faccette.profilo("ai literacy", Filtri(), Config(), client)
    assert len(profilo) == len(faccette.CAMPI)
    primo = profilo[0]
    assert primo["campo"] == faccette.CAMPI[0][0]
    assert primo["voci"][0]["etichetta"] == "2024"
    assert primo["voci"][0]["quota"] == 100      # il più alto riempie la barra
    assert primo["voci"][1]["quota"] == 25


@respx.mock
async def test_un_campo_che_fallisce_non_ferma_gli_altri():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        side_effect=[
            httpx.Response(500),
            *[httpx.Response(200, json=gruppi(("x", 1)))] * (len(faccette.CAMPI) - 1),
        ]
    )
    async with httpx.AsyncClient() as client:
        profilo = await faccette.profilo("ai literacy", Filtri(), Config(), client)
    assert profilo[0]["voci"] == []
    assert profilo[1]["voci"]


@respx.mock
async def test_i_filtri_valgono_anche_per_le_faccette():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=gruppi(("x", 1)))
    )
    async with httpx.AsyncClient() as client:
        await faccette.profilo("ai", Filtri(escludi_ritirati=True), Config(), client)
    assert "is_retracted%3Afalse" in str(rotta.calls[0].request.url)
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Esegui: `python -m pytest tests/test_faccette.py -v`
Atteso: FAIL con `ModuleNotFoundError: No module named 'ricerca.faccette'`.

- [ ] **Step 3: Scrivi `ricerca/faccette.py`**

```python
"""Com'è fatta la letteratura su un argomento, prima di leggerne un rigo.

`group_by` conta i risultati per anno, tipo, accesso, tema e paese: cinque
chiamate da $0.0001 che dicono se il campo è giovane o maturo, se è chiuso o
aperto, e da dove viene. Gli stessi numeri servono al diagramma PRISMA.
"""

from __future__ import annotations

import asyncio

import httpx

from . import openalex_api
from .config import Config
from .sources.openalex import filtro

# Campo dell'API, chiave i18n dell'etichetta.
CAMPI = (
    ("publication_year", "faccetta_anno"),
    ("type", "faccetta_tipo"),
    ("open_access.is_oa", "faccetta_accesso"),
    ("primary_topic.id", "faccetta_tema"),
    ("authorships.countries", "faccetta_paese"),
)


async def profilo(
    query: str,
    filtri,
    config: Config,
    client: httpx.AsyncClient,
    quanti: int = 12,
) -> list[dict]:
    """Un blocco per campo, con le voci già in scala per disegnare le barre."""

    stringa = filtro(query, filtri)
    esiti = await asyncio.gather(
        *(_uno(stringa, campo, config, client, quanti) for campo, _ in CAMPI),
        return_exceptions=True,
    )
    profilo = []
    for (campo, etichetta), esito in zip(CAMPI, esiti):
        voci = [] if isinstance(esito, Exception) else esito
        profilo.append({"campo": campo, "etichetta": etichetta, "voci": voci})
    return profilo


async def _uno(stringa: str, campo: str, config: Config, client, quanti: int) -> list[dict]:
    corpo = await openalex_api.chiama(
        client, "/works", config, filter=stringa, group_by=campo
    )
    gruppi = [g for g in corpo.get("group_by", []) if g.get("count")]
    gruppi.sort(key=lambda g: -g["count"])
    gruppi = gruppi[:quanti]
    massimo = gruppi[0]["count"] if gruppi else 1
    return [
        {
            "etichetta": g.get("key_display_name") or g.get("key") or "?",
            "quanti": g["count"],
            # La quota è la larghezza della barra, non una percentuale del
            # totale: serve a confrontare le voci fra loro.
            "quota": round(100 * g["count"] / massimo),
        }
        for g in gruppi
    ]
```

- [ ] **Step 4: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_faccette.py -v`
Atteso: PASS, tre test.

- [ ] **Step 5: Scrivi il partial e la rotta**

Crea `ricerca/templates/partials/faccette.html`:

```html
<div class="faccette">
  <p class="meta">{{ t.faccette_intro }}</p>
  {% for blocco in profilo %}
    <section>
      <h4>{{ t[blocco.etichetta] }}</h4>
      {% if not blocco.voci %}
        <p class="meta">{{ t.faccette_vuoto }}</p>
      {% else %}
        <ul class="barre">
          {% for voce in blocco.voci %}
            <li>
              <span class="etichetta">{{ voce.etichetta }}</span>
              <span class="barra" style="width: {{ voce.quota }}%"></span>
              <span class="numero">{{ voce.quanti }}</span>
            </li>
          {% endfor %}
        </ul>
      {% endif %}
    </section>
  {% endfor %}
</div>
```

Perché le faccette contino la stessa cosa che ha contato la ricerca, i filtri vanno salvati con la voce. In `ricerca/history.py`, dentro `salva`, aggiungi:

```python
        "filtri": asdict(strategy.filtri),
```

e una funzione che li rilegge, tollerante verso le cronologie scritte da versioni precedenti:

```python
def filtri(id_voce: str) -> Filtri:
    """I filtri di una ricerca salvata. Una voce vecchia non li ha: niente
    filtri è la risposta giusta, non un errore."""

    salvati = (voce(id_voce) or {}).get("filtri") or {}
    ammessi = set(Filtri.__dataclass_fields__)
    return Filtri(**{k: v for k, v in salvati.items() if k in ammessi})
```

importando `Filtri` da `.models`. Nel protocollo (`ricerca/export.py`, dentro `protocollo`), dopo i blocchi:

```python
    attivi = [f"{k}: {v}" for k, v in (voce.get("filtri") or {}).items() if v not in (None, False, "")]
    if attivi:
        righe += ["", "## Filtri", ""] + [f"- {riga}" for riga in attivi]
```

Poi la rotta, in `ricerca/app.py`:

```python
@app.get("/faccette/{id_ricerca}", response_class=HTMLResponse)
async def faccette_profilo(request: Request, id_ricerca: str):
    """Il profilo del campo per la strategia di questa ricerca."""

    config = current_config()
    voce = history.voce(id_ricerca) or {}
    query = next(
        (f.get("query", "") for f in voce.get("fonti", []) if f.get("id") == "openalex"), ""
    )
    if not query:
        return HTMLResponse("")
    async with cache.client(
        headers={"User-Agent": search.USER_AGENT}, follow_redirects=True
    ) as http:
        profilo = await faccette.profilo(query, history.filtri(id_ricerca), config, http)
    return templates.TemplateResponse(
        request, "partials/faccette.html", base_context(config, profilo=profilo)
    )
```

Aggiungi `faccette` alla riga di import di pacchetto. In `ricerca/templates/partials/risultati.html`, un bottone:

```html
<button hx-get="/faccette/{{ id_ricerca }}" hx-target="#faccette">{{ t.faccette_bottone }}</button>
<div id="faccette"></div>
```

CSS in `ricerca/static/` (nel foglio già presente):

```css
.barre { list-style: none; padding: 0; }
.barre li { display: grid; grid-template-columns: 12rem 1fr 4rem; align-items: center; gap: .5rem; }
.barre .barra { height: .7rem; background: currentColor; opacity: .35; border-radius: .35rem; }
.barre .numero { text-align: right; font-variant-numeric: tabular-nums; }
```

Chiavi i18n:

| chiave | it | en |
|---|---|---|
| `faccette_bottone` | Profilo del campo | Field profile |
| `faccette_intro` | Come si distribuiscono i risultati della stessa interrogazione su tutto OpenAlex, non solo sui record scaricati. | How the same query spreads across all of OpenAlex, not just the records fetched. |
| `faccette_vuoto` | Nessun dato per questo taglio. | No data for this breakdown. |
| `faccetta_anno` | Per anno | By year |
| `faccetta_tipo` | Per tipo di documento | By document type |
| `faccetta_accesso` | Accesso aperto | Open access |
| `faccetta_tema` | Per tema | By topic |
| `faccetta_paese` | Per paese degli autori | By author country |

- [ ] **Step 6: Scrivi il test della rotta e verificalo**

In `tests/test_faccette.py`:

```python
@respx.mock
def test_la_rotta_disegna_le_barre():
    from fastapi.testclient import TestClient
    from ricerca import history
    from ricerca.app import app
    from ricerca.models import Block, SourceResult, Strategy, Work

    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=gruppi(("2024", 40)))
    )
    id_ricerca = history.salva(
        "topic", Strategy(blocks=[Block("B", ["x"])]),
        [SourceResult("openalex", "OpenAlex", "title_and_abstract.search:x")],
        [Work(title="Uno")],
    )
    pagina = TestClient(app).get(f"/faccette/{id_ricerca}")
    assert pagina.status_code == 200
    assert "2024" in pagina.text


def test_una_voce_di_cronologia_senza_filtri_non_rompe_nulla():
    from ricerca import history
    from ricerca.models import Filtri

    assert history.filtri("id-che-non-esiste") == Filtri()
```

Esegui: `python -m pytest tests/test_faccette.py tests/test_i18n.py -q`
Atteso: PASS.

- [ ] **Step 7: Commit**

```bash
git add ricerca/faccette.py ricerca/app.py ricerca/i18n.py ricerca/templates/partials/ ricerca/static/ tests/test_faccette.py
git commit -m "feat: profilo del campo con le faccette di OpenAlex"
```

---

### Task 10: La fonte che cerca per significato

**Files:**
- Create: `ricerca/sources/openalex_semantica.py`
- Modify: `ricerca/sources/__init__.py:1-44`, `ricerca/i18n.py`
- Test: `tests/test_semantica.py`

**Interfaces:**
- Consumes: `openalex_api.chiama` (Task 2), `sources.openalex.SELECT` e `work_da` (Task 2), `strategy.flat_terms`.
- Produces: la fonte `openalex_semantica` nel registro (`sources.BY_ID`), fuori da `DEFAULT_SELECTED`.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `tests/test_semantica.py`:

```python
import httpx
import respx

from ricerca import sources
from ricerca.config import Config
from ricerca.models import Block, Filtri, Strategy

RISPOSTA = {"meta": {"cost_usd": 0.001}, "results": [{
    "id": "https://openalex.org/W3", "title": "Vicino di significato",
    "publication_year": 2025, "authorships": [], "primary_location": {},
}]}


def test_la_fonte_e_registrata_ma_spenta_di_suo():
    assert "openalex_semantica" in sources.BY_ID
    assert "openalex_semantica" not in sources.DEFAULT_SELECTED


def test_la_query_e_il_testo_dei_termini_non_i_booleani():
    fonte = sources.BY_ID["openalex_semantica"]
    strategy = Strategy(blocks=[
        Block("Uno", ["ai literacy", "AI competence"]),
        Block("Due", ["teacher"]),
    ])
    resa = fonte.render_query(strategy)
    assert "OR" not in resa
    assert "ai literacy" in resa
    assert "teacher" in resa


@respx.mock
async def test_cerca_con_il_parametro_semantico():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["openalex_semantica"].search(
            client, "insegnare l'intelligenza artificiale", 25, Config()
        )
    indirizzo = str(rotta.calls[0].request.url)
    assert "search.semantic=" in indirizzo
    assert works[0].title == "Vicino di significato"
    assert works[0].sources == ["openalex_semantica"]


@respx.mock
async def test_non_si_chiedono_piu_di_cinquanta_risultati():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        await sources.BY_ID["openalex_semantica"].search(client, "x", 200, Config())
    assert "per_page=50" in str(rotta.calls[0].request.url)


@respx.mock
async def test_i_filtri_di_anno_valgono_anche_qui():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        await sources.BY_ID["openalex_semantica"].search(
            client, "x", 10, Config(), Filtri(anno_da=2020, escludi_ritirati=True)
        )
    indirizzo = str(rotta.calls[0].request.url)
    assert "from_publication_date%3A2020-01-01" in indirizzo
    assert "is_retracted%3Afalse" in indirizzo


def test_l_avviso_spiega_il_costo():
    testo = sources.BY_ID["openalex_semantica"].avviso(Config(), "it")
    assert "50" in testo
```

- [ ] **Step 2: Esegui i test e verifica che falliscano**

Esegui: `python -m pytest tests/test_semantica.py -v`
Atteso: FAIL con `KeyError: 'openalex_semantica'`.

- [ ] **Step 3: Scrivi `ricerca/sources/openalex_semantica.py`**

```python
"""OpenAlex che cerca per significato invece che per parole.

`search.semantic` confronta il testo della domanda con l'abstract dei lavori
in uno spazio vettoriale: trova chi dice la stessa cosa con altre parole, che
è esattamente quello che una strategia booleana si lascia sfuggire. In cambio
restituisce al massimo cinquanta record e costa dieci volte un filtro, quindi
sta accanto alle altre fonti ma spenta finché non la si accende.
"""

from __future__ import annotations

import httpx

from .. import openalex_api
from ..config import Config
from ..i18n import strings
from ..models import Strategy
from ..strategy import flat_terms
from .base import Source
from .openalex import SELECT, filtro, work_da

MASSIMO = 50          # il tetto dell'endpoint, non una scelta nostra


class OpenAlexSemantica(Source):
    id = "openalex_semantica"
    label = "OpenAlex · significato"
    homepage = "https://openalex.org"

    def render_query(self, strategy: Strategy) -> str:
        """Qui i booleani non servono: conta il testo, più lungo è meglio è."""

        return flat_terms(strategy, limit=40)

    def avviso(self, config: Config, lang: str | None = None) -> str | None:
        return strings(lang)["semantica_avviso"]

    async def search(self, client: httpx.AsyncClient, query: str, limit: int, config: Config, filtri=None):
        # Il filtro di testo qui non va: la domanda viaggia in `search.semantic`.
        pezzi = [p for p in filtro("", filtri).split(",") if p and not p.startswith("title_and_abstract")]
        corpo = await openalex_api.chiama(
            client,
            "/works",
            config,
            **{"search.semantic": query},
            filter=",".join(pezzi),
            per_page=str(min(limit, MASSIMO)),
            select=SELECT,
        )
        works = [work_da(item) for item in corpo.get("results", [])]
        for work in works:
            work.sources = [self.id]
        return works
```

Attenzione: `filtro("", filtri)` produce `title_and_abstract.search:` come primo pezzo; la riga sopra lo scarta. Se ti sembra fragile, spezza `filtro` in `ricerca/sources/openalex.py` in due funzioni (`filtro_testo` e `filtro_vincoli`) e chiama qui solo la seconda — è la strada più pulita, falla se i test la reggono senza altre modifiche.

- [ ] **Step 4: Registra la fonte in `ricerca/sources/__init__.py`**

```python
from .openalex_semantica import OpenAlexSemantica
```

e dentro `ALL`, subito dopo `OpenAlex()`:

```python
    OpenAlexSemantica(),
```

`DEFAULT_SELECTED` non cambia.

Chiave i18n `semantica_avviso`:

| it | en |
|---|---|
| Cerca per significato: al massimo 50 record, $0.001 a interrogazione. Utile quando le parole giuste non si sanno ancora. | Meaning-based search: 50 records at most, $0.001 per query. Useful when you don't know the right words yet. |

- [ ] **Step 5: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_semantica.py tests/test_sources.py tests/test_stato_fonti.py tests/test_i18n.py -q`
Atteso: PASS. Se `test_stato_fonti.py` conta le fonti, aggiorna il numero atteso.

- [ ] **Step 6: Commit**

```bash
git add ricerca/sources/ ricerca/i18n.py tests/test_semantica.py
git commit -m "feat: OpenAlex che cerca per significato, accanto alle altre fonti"
```

---

### Task 11: Autocomplete

**Files:**
- Modify: `ricerca/openalex_api.py` (funzione `autocompleta`), `ricerca/app.py` (rotta), `ricerca/templates/partials/strategia.html`, `ricerca/i18n.py`
- Test: `tests/test_autocomplete.py`

**Interfaces:**
- Consumes: `openalex_api.chiama` (Task 2).
- Produces: `openalex_api.autocompleta(entita: str, q: str, config: Config, client: httpx.AsyncClient) -> list[dict]` con chiavi `id`, `nome`, `nota`; rotta `GET /autocompleta`.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `tests/test_autocomplete.py`:

```python
import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import openalex_api
from ricerca.app import app
from ricerca.config import Config

RISPOSTA = {"meta": {"cost_usd": 0.0}, "results": [
    {"id": "https://openalex.org/S9692511", "display_name": "Frontiers in Psychology",
     "hint": "Frontiers Media", "entity_type": "source"},
]}


@respx.mock
async def test_l_autocomplete_restituisce_id_e_nome():
    respx.get(url__startswith="https://api.openalex.org/autocomplete/sources").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        voci = await openalex_api.autocompleta("sources", "front", Config(), client)
    assert voci[0]["id"] == "S9692511"
    assert voci[0]["nome"] == "Frontiers in Psychology"
    assert voci[0]["nota"] == "Frontiers Media"


@respx.mock
async def test_un_entita_non_prevista_non_parte():
    rotta = respx.get(url__startswith="https://api.openalex.org/autocomplete").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        voci = await openalex_api.autocompleta("../segreti", "x", Config(), client)
    assert voci == []
    assert not rotta.called


@respx.mock
async def test_una_domanda_troppo_corta_non_parte():
    rotta = respx.get(url__startswith="https://api.openalex.org/autocomplete").mock(
        return_value=httpx.Response(200, json=RISPOSTA)
    )
    async with httpx.AsyncClient() as client:
        assert await openalex_api.autocompleta("sources", "f", Config(), client) == []
    assert not rotta.called


@respx.mock
def test_la_rotta_rende_le_opzioni():
    respx.get(url__startswith="https://api.openalex.org/autocomplete/keywords").mock(
        return_value=httpx.Response(200, json={"meta": {}, "results": [
            {"id": "https://openalex.org/keywords/ai-literacy",
             "display_name": "AI literacy", "hint": ""},
        ]})
    )
    pagina = TestClient(app).get("/autocompleta", params={"entita": "keywords", "q": "ai li"})
    assert pagina.status_code == 200
    assert "AI literacy" in pagina.text


@respx.mock
def test_se_openalex_e_giu_la_rotta_risponde_vuota():
    respx.get(url__startswith="https://api.openalex.org/autocomplete").mock(
        return_value=httpx.Response(500)
    )
    pagina = TestClient(app).get("/autocompleta", params={"entita": "keywords", "q": "ai li"})
    assert pagina.status_code == 200
    assert pagina.text.strip() == ""
```

- [ ] **Step 2: Esegui i test e verifica che falliscano**

Esegui: `python -m pytest tests/test_autocomplete.py -v`
Atteso: FAIL con `AttributeError: module 'ricerca.openalex_api' has no attribute 'autocompleta'`.

- [ ] **Step 3: Scrivi `autocompleta` in `ricerca/openalex_api.py`**

```python
# Le entità su cui l'applicazione suggerisce: la lista chiusa evita che un
# parametro dell'interfaccia diventi un pezzo di indirizzo qualsiasi.
ENTITA = ("keywords", "topics", "sources", "institutions", "funders", "authors")
MINIMO = 2


async def autocompleta(entita: str, q: str, config: Config, client: httpx.AsyncClient) -> list[dict]:
    """Suggerimenti mentre si scrive: ~200 ms e non costa nulla.

    Serve anche a rispettare la regola dei documenti di OpenAlex — mai
    filtrare per nome, sempre risolvere il nome in un identificativo.
    """

    if entita not in ENTITA or len(q.strip()) < MINIMO:
        return []
    corpo = await chiama(client, f"/autocomplete/{entita}", config, q=q.strip(), timeout=10)
    return [
        {
            "id": id_breve(voce.get("id")),
            "nome": str(voce.get("display_name") or ""),
            "nota": str(voce.get("hint") or ""),
        }
        for voce in corpo.get("results", [])
        if voce.get("display_name")
    ]
```

- [ ] **Step 4: Scrivi la rotta in `ricerca/app.py`**

```python
@app.get("/autocompleta", response_class=HTMLResponse)
async def autocompleta(request: Request, entita: str = "keywords", q: str = ""):
    """Le opzioni di un `datalist`: il valore è l'identificativo, l'etichetta
    il nome. Un guasto di OpenAlex qui non deve interrompere la scrittura."""

    config = current_config()
    try:
        async with cache.client(headers={"User-Agent": search.USER_AGENT}) as http:
            voci = await openalex_api.autocompleta(entita, q, config, http)
    except (httpx.HTTPError, OSError):
        voci = []
    return templates.TemplateResponse(
        request, "partials/opzioni.html", {"request": request, "voci": voci}
    )
```

Aggiungi `openalex_api` alla riga di import di pacchetto. Crea `ricerca/templates/partials/opzioni.html`:

```html
{% for voce in voci %}<option value="{{ voce.id }}" label="{{ voce.nome }}{% if voce.nota %} — {{ voce.nota }}{% endif %}">{{ voce.nome }}</option>
{% endfor %}
```

- [ ] **Step 5: Attacca i suggerimenti ai campi dei termini**

In `ricerca/templates/partials/strategia.html`, per ogni casella dei termini:

```html
<input name="terms" list="suggerimenti-{{ loop.index }}"
       hx-get="/autocompleta?entita=keywords"
       hx-trigger="keyup changed delay:300ms"
       hx-vals='js:{q: event.target.value}'
       hx-target="#suggerimenti-{{ loop.index }}">
<datalist id="suggerimenti-{{ loop.index }}"></datalist>
```

Il valore viaggia in `hx-vals` e non in `hx-params` perché il campo si chiama `terms`, mentre la rotta aspetta `q`. Dopo il test automatico, prova a mano nel browser: `datalist` è l'unico pezzo di questa fase che nessun test copre davvero.

- [ ] **Step 6: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_autocomplete.py -q`
Atteso: PASS, cinque test.

- [ ] **Step 7: Commit**

```bash
git add ricerca/openalex_api.py ricerca/app.py ricerca/templates/partials/ tests/test_autocomplete.py
git commit -m "feat: suggerimenti dei termini dall'autocomplete di OpenAlex"
```

---

### Task 12: Filtri per rivista, ateneo, finanziatore

**Files:**
- Modify: `ricerca/models.py` (`Filtri`), `ricerca/sources/openalex.py` (`filtro`), `ricerca/strategy.py` (`strategy_from_form`), `ricerca/app.py` (rotte `query` e `cerca`), `ricerca/templates/partials/strategia.html`, `ricerca/i18n.py`
- Test: `tests/test_filtri_entita.py`

**Interfaces:**
- Consumes: `openalex_api.autocompleta` (Task 11), `Filtri` (Task 4).
- Produces: `Filtri.rivista_id: str`, `Filtri.ateneo_id: str`, `Filtri.finanziatore_id: str`; `strategy.identificativo(valore: str, prefisso: str) -> str`.

Nomi dei filtri verificati sull'API il 2026-08-20: `primary_location.source.id`, `authorships.institutions.id`, `funders.id`. `grants.funder` e `awards.funder.id` **non** esistono: rispondono `400`.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `tests/test_filtri_entita.py`:

```python
from ricerca.models import Filtri
from ricerca.sources.openalex import filtro
from ricerca.strategy import identificativo, strategy_from_form


def test_gli_identificativi_entrano_nel_filtro():
    reso = filtro("x", Filtri(
        rivista_id="S9692511", ateneo_id="I27837315", finanziatore_id="F4320306076"
    ))
    assert "primary_location.source.id:S9692511" in reso
    assert "authorships.institutions.id:I27837315" in reso
    assert "funders.id:F4320306076" in reso


def test_un_nome_scritto_a_mano_non_diventa_un_filtro():
    assert identificativo("Frontiers in Psychology", "S") == ""
    assert identificativo("S9692511", "S") == "S9692511"
    assert identificativo("s9692511", "S") == "S9692511"
    assert identificativo("I123", "S") == ""
    assert identificativo("", "S") == ""


def test_il_modulo_scarta_quello_che_non_e_un_identificativo():
    strategy = strategy_from_form(
        ["B"], ["ai"], rivista="Frontiers in Psychology", ateneo="I27837315", finanziatore=""
    )
    assert strategy.filtri.rivista_id == ""
    assert strategy.filtri.ateneo_id == "I27837315"
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Esegui: `python -m pytest tests/test_filtri_entita.py -v`
Atteso: FAIL con `TypeError: Filtri.__init__() got an unexpected keyword argument 'rivista_id'`.

- [ ] **Step 3: Estendi `Filtri` e `filtro`**

In `ricerca/models.py`, dentro `Filtri`, dopo `con_pdf: bool = False`:

```python
    rivista_id: str = ""
    ateneo_id: str = ""
    finanziatore_id: str = ""
```

e in `attivi()` aggiungi `or self.rivista_id or self.ateneo_id or self.finanziatore_id`.

In `ricerca/sources/openalex.py`, dentro `filtro`, dopo i filtri booleani:

```python
    if filtri and filtri.rivista_id:
        pezzi.append(f"primary_location.source.id:{filtri.rivista_id}")
    if filtri and filtri.ateneo_id:
        pezzi.append(f"authorships.institutions.id:{filtri.ateneo_id}")
    if filtri and filtri.finanziatore_id:
        pezzi.append(f"funders.id:{filtri.finanziatore_id}")
```

- [ ] **Step 4: Aggiungi `identificativo` a `ricerca/strategy.py`**

```python
import re

_IDENTIFICATIVO = re.compile(r"^([SIF])(\d+)$", re.IGNORECASE)


def identificativo(valore: str, prefisso: str) -> str:
    """Un identificativo OpenAlex, o niente.

    Il campo del modulo accetta anche quello che si scrive a mano: un nome
    di rivista battuto a tastiera non è un filtro valido, e mandarlo così
    farebbe rispondere `400` a OpenAlex. Meglio ignorarlo.
    """

    trovato = _IDENTIFICATIVO.match(str(valore).strip())
    if not trovato or trovato.group(1).upper() != prefisso:
        return ""
    return prefisso + trovato.group(2)
```

e in `strategy_from_form` tre parametri nuovi (`rivista: str = ""`, `ateneo: str = ""`, `finanziatore: str = ""`) che nel `Filtri(...)` diventano:

```python
            rivista_id=identificativo(rivista, "S"),
            ateneo_id=identificativo(ateneo, "I"),
            finanziatore_id=identificativo(finanziatore, "F"),
```

- [ ] **Step 5: Passa i campi dalle rotte e mettili nel modulo**

In `ricerca/app.py`, sia in `query` sia in `cerca`, aggiungi `rivista: str = Form(default="")`, `ateneo: str = Form(default="")`, `finanziatore: str = Form(default="")` e passali a `strategy_from_form`.

In `ricerca/templates/partials/strategia.html`, dentro il `fieldset` dei filtri OpenAlex:

```html
{% for campo, entita, etichetta in [("rivista", "sources", t.filtro_rivista), ("ateneo", "institutions", t.filtro_ateneo), ("finanziatore", "funders", t.filtro_finanziatore)] %}
  <label>{{ etichetta }}
    <input name="{{ campo }}" list="lista-{{ campo }}" placeholder="{{ t.filtro_entita_aiuto }}"
           hx-get="/autocompleta?entita={{ entita }}"
           hx-trigger="keyup changed delay:300ms"
           hx-vals='js:{q: event.target.value}'
           hx-target="#lista-{{ campo }}">
    <datalist id="lista-{{ campo }}"></datalist>
  </label>
{% endfor %}
```

Chiavi i18n:

| chiave | it | en |
|---|---|---|
| `filtro_rivista` | Rivista | Journal |
| `filtro_ateneo` | Ateneo | Institution |
| `filtro_finanziatore` | Finanziatore | Funder |
| `filtro_entita_aiuto` | scrivi il nome e scegli dall'elenco | type the name and pick from the list |

- [ ] **Step 6: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_filtri_entita.py tests/test_filtri.py tests/test_i18n.py -q`
Atteso: PASS.

- [ ] **Step 7: Commit**

```bash
git add ricerca/models.py ricerca/sources/openalex.py ricerca/strategy.py ricerca/app.py ricerca/i18n.py ricerca/templates/partials/strategia.html tests/test_filtri_entita.py
git commit -m "feat: filtri per rivista, ateneo e finanziatore risolti in identificativi"
```

---

### Task 13: Campione riproducibile e paginazione a cursore

**Files:**
- Modify: `ricerca/models.py` (`Filtri`), `ricerca/sources/openalex.py` (`search`), `ricerca/strategy.py`, `ricerca/app.py`, `ricerca/export.py` (il seme nel protocollo), `ricerca/templates/partials/strategia.html`, `ricerca/i18n.py`
- Test: `tests/test_campione.py`

**Interfaces:**
- Consumes: `Filtri` (Task 4), `openalex_api.chiama` (Task 2).
- Produces: `Filtri.campione: int | None`, `Filtri.seme: int | None`; `OpenAlex.search` pagina con il cursore fino a `limit`, tetto 200.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `tests/test_campione.py`:

```python
import httpx
import respx

from ricerca import sources
from ricerca.config import Config
from ricerca.models import Filtri


def pagina(ids, cursore=None):
    return {
        "meta": {"cost_usd": 0.0001, "next_cursor": cursore},
        "results": [
            {"id": f"https://openalex.org/{i}", "title": str(i),
             "authorships": [], "primary_location": {}} for i in ids
        ],
    }


@respx.mock
async def test_oltre_cento_record_si_pagina_col_cursore():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        side_effect=[
            httpx.Response(200, json=pagina([f"W{n}" for n in range(100)], "IlsxMDAu")),
            httpx.Response(200, json=pagina([f"X{n}" for n in range(50)], None)),
        ]
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["openalex"].search(client, "q", 150, Config())
    assert len(works) == 150


@respx.mock
async def test_il_cursore_si_ferma_al_tetto():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=pagina([f"W{n}" for n in range(100)], "ancora"))
    )
    async with httpx.AsyncClient() as client:
        works = await sources.BY_ID["openalex"].search(client, "q", 999, Config())
    assert len(works) <= 200


@respx.mock
async def test_il_campione_e_una_chiamata_sola_con_il_seme():
    rotta = respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=pagina(["W1", "W2"], "ancora"))
    )
    async with httpx.AsyncClient() as client:
        await sources.BY_ID["openalex"].search(
            client, "q", 150, Config(), Filtri(campione=20, seme=7)
        )
    assert len(rotta.calls) == 1
    indirizzo = str(rotta.calls[0].request.url)
    assert "sample=20" in indirizzo
    assert "seed=7" in indirizzo
    assert "cursor" not in indirizzo


def test_il_modulo_legge_campione_e_seme():
    from ricerca.strategy import strategy_from_form

    filtri = strategy_from_form(["B"], ["ai"], campione="50", seme="7").filtri
    assert filtri.campione == 50
    assert filtri.seme == 7
    vuoti = strategy_from_form(["B"], ["ai"], campione="", seme="x").filtri
    assert vuoti.campione is None
    assert vuoti.seme is None
```

- [ ] **Step 2: Esegui i test e verifica che falliscano**

Esegui: `python -m pytest tests/test_campione.py -v`
Atteso: FAIL — `Filtri` non ha `campione`, e `search` fa una chiamata sola.

- [ ] **Step 3: Estendi `Filtri`**

In `ricerca/models.py`, dentro `Filtri`:

```python
    # Pilota di screening riproducibile: stesso seme, stesso campione.
    campione: int | None = None
    seme: int | None = None
```

`attivi()` non cambia: un campione non è un vincolo sui risultati, è un modo di guardarli.

- [ ] **Step 4: Pagina con il cursore in `ricerca/sources/openalex.py`**

`search` diventa:

```python
TETTO = 200          # oltre non si va: il costo deve restare prevedibile
PER_PAGINA = 100     # il massimo per chiamata


class OpenAlex(Source):
    ...

    async def search(self, client: httpx.AsyncClient, query: str, limit: int, config: Config, filtri=None):
        quanti = min(limit, TETTO)
        stringa = filtro(query, filtri)

        if filtri and filtri.campione:
            corpo = await openalex_api.chiama(
                client, "/works", config,
                filter=stringa,
                sample=str(min(filtri.campione, quanti)),
                seed=str(filtri.seme) if filtri.seme is not None else "",
                per_page=str(min(filtri.campione, quanti, PER_PAGINA)),
                select=SELECT,
            )
            return [work_da(item) for item in corpo.get("results", [])]

        works, cursore = [], "*"
        while cursore and len(works) < quanti:
            corpo = await openalex_api.chiama(
                client, "/works", config,
                filter=stringa,
                per_page=str(min(quanti - len(works), PER_PAGINA)),
                cursor=cursore,
                select=SELECT,
            )
            risultati = corpo.get("results", [])
            works.extend(work_da(item) for item in risultati)
            cursore = (corpo.get("meta") or {}).get("next_cursor") if risultati else None
        return works[:quanti]
```

- [ ] **Step 5: Leggi campione e seme dal modulo**

In `ricerca/strategy.py`, due parametri nuovi in `strategy_from_form` (`campione: str = ""`, `seme: str = ""`) e nel `Filtri(...)`:

```python
            campione=_numero(campione, massimo=10000),
            seme=_numero(seme, massimo=999999),
```

con:

```python
def _numero(valore: str, massimo: int) -> int | None:
    valore = str(valore).strip()
    if not valore.isdigit() or not 1 <= int(valore) <= massimo:
        return None
    return int(valore)
```

In `ricerca/app.py`, `campione: str = Form(default="")` e `seme: str = Form(default="")` nelle rotte `query` e `cerca`, passati a `strategy_from_form`.

- [ ] **Step 6: Segna il seme nel protocollo**

Campione e seme stanno già in `Filtri`, che il Task 9 salva per intero nella voce (`voce["filtri"]`): non serve aggiungere altre chiavi alla cronologia. Basta stamparli in evidenza, perché un campione cambia il senso di tutti i numeri che seguono. In `ricerca/export.py`, dentro `protocollo`, subito dopo la data:

```python
    campione = (voce.get("filtri") or {}).get("campione")
    if campione:
        seme = (voce.get("filtri") or {}).get("seme") or "—"
        righe += [f"Campione casuale: {campione} record, seme {seme}", ""]
```

e la riga corrispondente, senza marcatura, in `protocollo_testo`.

Se il Task 9 non è ancora stato fatto, aggiungi prima `"filtri": asdict(strategy.filtri),` alla voce in `ricerca/history.py::salva`.

- [ ] **Step 7: Metti i campi nel modulo**

In `ricerca/templates/partials/strategia.html`, nel `fieldset` dei filtri OpenAlex:

```html
<label>{{ t.campione }} <input name="campione" type="number" min="1" max="10000" placeholder="{{ t.campione_vuoto }}"></label>
<label>{{ t.seme }} <input name="seme" type="number" min="1" placeholder="7"></label>
```

Chiavi i18n:

| chiave | it | en |
|---|---|---|
| `campione` | Campione casuale | Random sample |
| `campione_vuoto` | tutti | all |
| `seme` | Seme | Seed |

- [ ] **Step 8: Esegui i test e verifica che passino**

Esegui: `python -m pytest tests/test_campione.py tests/test_sources.py tests/test_record_openalex.py tests/test_i18n.py -q`
Atteso: PASS. I test vecchi che si aspettano `per_page=25` o una chiamata sola vanno aggiornati alla forma nuova: la paginazione a cursore è il comportamento voluto.

- [ ] **Step 9: Esegui tutta la suite**

Esegui: `python -m pytest -q`
Atteso: PASS.

- [ ] **Step 10: Commit**

```bash
git add ricerca/models.py ricerca/sources/openalex.py ricerca/strategy.py ricerca/app.py ricerca/history.py ricerca/export.py ricerca/i18n.py ricerca/templates/partials/strategia.html tests/test_campione.py
git commit -m "feat: campione riproducibile e risultati oltre i cento per chiamata"
```

---

## Chiusura

- [ ] **Aggiorna il README** (sezione italiana e inglese): filtri nuovi, snowballing, profilo del campo, ricerca semantica, PDF dall'archivio, credito visibile.
- [ ] **Aggiorna `docs/design.md`** con il ruolo di `openalex_api.py` come unica porta verso OpenAlex.
- [ ] **Esegui i test a contratto**: `python -m pytest -m rete -q` (spende qualche millesimo di dollaro).
- [ ] **Prova a mano**: una ricerca completa, uno snowballing, un profilo del campo, un PDF dall'archivio con l'opzione accesa e una con l'opzione spenta.
- [ ] **Alza la versione** in `pyproject.toml` e nota le novità dove il progetto le annota.
