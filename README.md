# Ricerca

**Italiano** · [English](#english)

Assistente di strategia di ricerca bibliografica. Da un argomento ricava
parole chiave, termini controllati e stringhe di ricerca pronte per ogni
banca dati, poi esegue le query ed esporta i risultati.

![Ricerche suggerite](docs/screenshot/2-ricerche-suggerite.png)

## Come funziona

1. **Argomento** — lo scrivi in italiano o in inglese.
2. **Ricerche suggerite** — concetti da OpenAlex, termini MeSH da PubMed,
   termini che ricorrono nei titoli dei primi risultati. Da questi nascono i
   blocchi booleani, modificabili a mano, e le stringhe per ogni motore.
   Nessuna ricerca parte finché non la avvii tu.
3. **Risultati** — le fonti scelte vengono interrogate in parallelo, i
   duplicati uniti per DOI o titolo, l'elenco esportato in `.bib` o `.csv`.

Motori interrogati: OpenAlex, PubMed, Europe PMC, arXiv, DOAJ, Semantic
Scholar (meglio con chiave), CORE (chiave gratuita), OPAC SBN per i libri
italiani (tramite la CLI `opac-sbn-pp-cli`, se installata). Per Scopus e Web
of Science l'app produce la stringa da incollare nella loro interfaccia.

## Installazione

Serve solo **Python 3.11 o superiore**. Scarica il progetto e avvialo:

| Sistema | Comando |
|---|---|
| Linux, macOS | doppio clic su `avvia.sh`, oppure `./avvia.sh` dal terminale |
| Windows | doppio clic su `avvia.bat` |

Il lanciatore prepara l'ambiente la prima volta e apre il browser su
`http://127.0.0.1:8000` (o la prima porta libera). Il server ascolta solo su
`127.0.0.1`: non è raggiungibile da altre macchine.

In alternativa, da terminale:

```bash
uv run ricerca serve          # oppure: pip install -e . && ricerca serve
```

## Chiavi ed email: tutto dall'interfaccia

Nessuna chiave è obbligatoria e nessuna va scritta in un file a mano.
Dalla pagina **Impostazioni**:

- **email di cortesia** — OpenAlex la usa per concedere limiti di richiesta
  più larghi; senza, risponde spesso `429`. Si può inserire anche dalla
  pagina iniziale, al primo avvio;
- **chiave Semantic Scholar**, **chiave CORE**, **chiave NCBI/PubMed**;
- **endpoint e modello LLM** (facoltativi).

Le chiavi restano in `~/.ricerca/config.toml` con permessi `600`, non
vengono mai rimandate al browser e si cancellano con la spunta *rimuovi*.

## LLM (facoltativo)

Un endpoint compatibile con l'API OpenAI — Ollama
(`http://localhost:11434/v1`), llama-swap, DeepSeek, OpenAI. Serve solo a
riorganizzare i termini in blocchi concettuali: senza, l'app costruisce i
blocchi dai soli dati e funziona lo stesso.

## Lingua

L'interfaccia è in italiano e in inglese: si cambia con i pulsanti `IT` /
`EN` in alto a destra e la scelta resta memorizzata.

## Sviluppo

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest -q                     # 70 test, nessuno tocca la rete
.venv/bin/uvicorn ricerca.app:app --reload --port 8000
```

Un solo pacchetto Python: FastAPI rende HTML con Jinja2, htmx aggiorna i
frammenti di pagina. Niente Node, niente build, niente binari da firmare.

- `ricerca/keywords.py` — estrazione dei termini dalle banche dati
- `ricerca/strategy.py` — blocchi booleani e resa per motore
- `ricerca/sources/` — un modulo per motore, interfaccia unica
- `ricerca/search.py` — esecuzione parallela con isolamento degli errori
- `ricerca/i18n.py` — stringhe italiane e inglesi
- `docs/specs/` — il documento di progetto

---

# English

A literature search strategy assistant. From a topic it derives keywords,
controlled vocabulary terms and ready-made query strings for each database,
then runs the queries and exports the results.

## How it works

1. **Topic** — write it in English or Italian.
2. **Suggested searches** — concepts from OpenAlex, MeSH terms from PubMed,
   terms recurring in the titles of the first results. These become editable
   boolean blocks and one query string per engine. No search runs until you
   start it.
3. **Results** — the selected sources are queried in parallel, duplicates
   merged by DOI or title, the list exported as `.bib` or `.csv`.

Sources queried: OpenAlex, PubMed, Europe PMC, arXiv, DOAJ, Semantic Scholar
(better with a key), CORE (free key), OPAC SBN for Italian books (through the
`opac-sbn-pp-cli` CLI, if installed). For Scopus and Web of Science the app
produces the string to paste into their own interface.

## Install

All you need is **Python 3.11+**. Download the project and start it:

| System | Command |
|---|---|
| Linux, macOS | double-click `avvia.sh`, or run `./avvia.sh` |
| Windows | double-click `avvia.bat` |

The launcher prepares the environment on first run and opens the browser at
`http://127.0.0.1:8000` (or the first free port). The server listens on
`127.0.0.1` only.

From a terminal instead:

```bash
uv run ricerca serve          # or: pip install -e . && ricerca serve
```

## Keys and email: all from the interface

No key is required, and none has to be written into a file by hand. On the
**Settings** page you can set the courtesy email (OpenAlex grants higher rate
limits with it; without it, it often answers `429`), the Semantic Scholar,
CORE and NCBI keys, and an optional LLM endpoint and model.

Keys are stored in `~/.ricerca/config.toml` with `600` permissions, are never
sent back to the browser, and can be deleted with the *remove* checkbox.

## Language

The interface is available in Italian and English: switch with the `IT` / `EN`
buttons in the header. The choice is remembered.
