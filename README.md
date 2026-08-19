# Ricerca

**Italiano** · [English](#english)

Assistente di strategia di ricerca bibliografica. Da un argomento ricava
parole chiave, termini controllati e stringhe di ricerca pronte per ogni
banca dati, poi esegue le query ed esporta i risultati.

![Ricerche suggerite](docs/screenshot/2-ricerche-suggerite.png)

## Prima apertura

Al primo avvio si apre una **configurazione guidata**: spiega a che serve
ogni impostazione e che cosa cambia se la lasci vuota. C'è come installare
**Ollama**, quali modelli reggono *questa* macchina (li sceglie guardando
memoria e processore) e i comandi già pronti da copiare — dai tagli piccoli
di **Gemma 4** per le macchine modeste fino a **qwen3.8** dove c'è memoria a
sufficienza — oltre alle alternative in rete: **DeepSeek** e **OpenAI**, con
indirizzi, modelli e dove si prende la chiave. Si può saltare e configurare dopo; si rivede quando
si vuole da Impostazioni.

## Come funziona

1. **Argomento** — lo scrivi in italiano o in inglese.
2. **Ricerche suggerite** — concetti da OpenAlex, termini MeSH da PubMed,
   termini che ricorrono nei titoli dei primi risultati. Da questi nascono i
   blocchi booleani, modificabili a mano, e le stringhe per ogni motore.
   Nessuna ricerca parte finché non la avvii tu.
3. **Risultati** — le fonti scelte vengono interrogate in parallelo, i
   duplicati uniti per DOI o titolo (anche quando un titolo è troncato o
   punteggiato diversamente), l'elenco ordinato per pertinenza. Scegli quali
   campi mostrare, leggi come tabella o come **riferimenti APA**, scarica i
   **PDF ad accesso aperto**, esporta in `.bib`, `.csv`, `.txt`.
4. **Che cosa ha fatto ogni banca dati** — la stringa esattamente com'è stata
   inviata, quanti record ha portato, quanti ne sono rimasti dopo la deduplica,
   quanti li ha trovati **solo lei** e in quanto tempo.
5. **Selezione** — ogni record si marca *incluso*, *forse* o *escluso* con un
   motivo, uno per volta o **in blocco** sui record spuntati — includi, forse,
   escludi, annulla le decisioni, manda a Zotero, scarica i PDF aperti. Ogni
   riga ha il suo tasto **PDF**; quelli scaricati si portano via tutti insieme
   in uno **zip**, con il nome della chiave di citazione. I conteggi seguono il diagramma di flusso PRISMA e
   il **protocollo** raccoglie stringhe, numeri e decisioni per la sezione
   «Metodo», in Markdown o in testo semplice.
6. **Cronologia** — ogni ricerca resta salvata con la sua strategia e i suoi
   record: si riapre, si riesporta e se ne scaricano i PDF senza ripeterla.
7. **Biblioteca** — i PDF scaricati sono cercabili a testo pieno.

In fondo a ogni pagina c'è **il registro di quel che l'app sta facendo**: una
riga per banca dati con la stringa inviata, i record trovati e il tempo, e in
rosso ciò che non ha funzionato. Nessun errore resta muto: anche i guasti
imprevisti finiscono lì e in `~/.ricerca/attivita.log`.

Ricerche e scaricamenti **proseguono sul server**: si può cambiare pagina e
tornare, o chiudere il pannello — il lavoro non si ferma e la ricerca finita
si ritrova in cronologia.

Limiti di anno e «solo articoli di rivista» valgono per tutte le fonti,
ognuna con la propria sintassi. Le risposte restano in una cache locale di un
giorno: affinare una strategia non ribatte sulle API.

Motori interrogati: OpenAlex, Crossref, PubMed, Europe PMC, arXiv, DOAJ,
Semantic Scholar (meglio con chiave), CORE (chiave gratuita), OPAC SBN per i
libri italiani (tramite la CLI `opac-sbn-pp-cli`, se installata). Per Scopus e Web
of Science l'app produce la stringa da incollare nella loro interfaccia.

## Scarica e avvia

Dalla pagina [Releases](https://github.com/nugh75/Ricerca-scientifica/releases)
scarica l'archivio del tuo sistema, estrailo e avvia:

| Sistema | Archivio | Avvio |
|---|---|---|
| macOS | `ricerca-*-macos.tar.gz` | trascina **Ricerca.app** in Applicazioni; la prima volta clic destro → *Apri* |
| Windows | `ricerca-*-windows.zip` | doppio clic su `avvia.bat` — `crea-scorciatoia-windows.bat` mette l'icona sul Desktop |
| Linux | `ricerca-*-linux.tar.gz` | `./avvia.sh` — `installa-scorciatoia-linux.sh` la mette nel menu applicazioni |

Su macOS l'app è un vero bundle: si avvia dall'icona, **senza finestra di
Terminale**. Se macOS la dichiara «danneggiata» (succede agli archivi
scaricati e non firmati), una volta sola:

```bash
xattr -dr com.apple.quarantine /Applications/Ricerca.app
```

**Chiudendo la pagina del browser l'app si chiude da sola** entro una decina
di secondi: non resta nessun processo appeso e non serve un terminale per
fermarla. Per tenerla accesa anche a pagina chiusa: `ricerca serve --resta-aperto`.

**Non serve installare Python.** Al primo avvio il lanciatore scarica `uv`
dentro la cartella dell'app e con esso l'interprete e le librerie: nessun
permesso di amministratore, nessuna modifica al sistema, nessun `PATH` da
sistemare. Serve solo una connessione a internet la prima volta.

Se la cartella non è scrivibile (per esempio `/Applications` o
`Program Files`), l'ambiente viene creato in `~/.ricerca` e la cartella
dell'app resta intatta.

**Aggiornare**: scarica il nuovo archivio e avvialo. Il lanciatore confronta
la versione con quella già installata e rifà l'ambiente se serve.

La versione in esecuzione è scritta in fondo a ogni pagina, e in
**Impostazioni** c'è *Quale copia sta girando*: versione, cartella dell'app,
ambiente installato. Se la versione non cambia dopo un aggiornamento, quella
riga dice perché — quasi sempre si sta aprendo una copia vecchia dell'app.
Su macOS conviene cancellare la vecchia `Ricerca.app` prima di copiare la
nuova, e svuotare il Cestino. Il registro del primo avvio è in
`~/.ricerca/avvio.log`.

Ricerca si apre in una **finestra propria**, senza barra degli indirizzi né
schede: il lanciatore cerca un browser della famiglia Chromium (Chrome, Edge,
Brave, Chromium, Vivaldi) e lo avvia in modo applicazione. Se non ne trova
nessuno, apre il browser predefinito; con `ricerca serve --scheda` si chiede
apposta una scheda normale.

Con Safari, che non ha quel modo, la finestra si ottiene una volta sola:
**Condividi → Aggiungi al Dock**. Su Chrome ed Edge lo stesso risultato si ha
da **Installa applicazione** nella barra degli indirizzi. Da lì Ricerca compare
fra le applicazioni con la sua icona.

Il server ascolta solo su `127.0.0.1`: non è raggiungibile da altre macchine.

Da terminale, se preferisci:

```bash
uv run ricerca serve          # oppure: pip install -e . && ricerca serve
```

Per costruire gli archivi: `./scripts/crea-release.sh` (finiscono in `dist/`).
In CI li produce `.github/workflows/release.yml` a ogni tag `v*`.

## Chiavi ed email: tutto dall'interfaccia

Dal 2026 OpenAlex misura le richieste. Senza chiave si usa la corsia anonima,
che ha un budget giornaliero e poi risponde `429`; la **chiave è gratuita** e
si richiede in un minuto su [openalex.org/rest-api](https://openalex.org/rest-api).
È il singolo campo che più cambia la qualità dei suggerimenti.

L'app fa comunque **una sola** chiamata per suggerimento: temi e parole chiave
si leggono nei primi cinquanta risultati invece di chiamare gli endpoint
`/text/*`, che costano dieci volte tanto. L'email di cortesia resta utile e viene spedita solo se è un
indirizzo valido: un `mailto` malformato fa rispondere `400`.

Nessuna chiave è obbligatoria e nessuna va scritta in un file a mano.
Dalla pagina **Impostazioni**:

- **email di cortesia** — OpenAlex la usa per concedere limiti di richiesta
  più larghi; senza, risponde spesso `429`. Si può inserire anche dalla
  pagina iniziale, al primo avvio;
- **chiave OpenAlex** (gratuita), **chiave Semantic Scholar**, **chiave CORE**,
  **chiave NCBI/PubMed**;
- **chiave e libreria Zotero**, per spedire i record inclusi nella tua
  libreria con un bottone;
- **endpoint e modello LLM** (facoltativi: servono anche a tradurre un topic
  italiano prima di interrogare PubMed, che in italiano non trova i MeSH).

Le chiavi restano in `~/.ricerca/config.toml` con permessi `600`, non
vengono mai rimandate al browser e si cancellano con la spunta *rimuovi*.
Nella stessa cartella stanno la cronologia (`cronologia.json`) e i PDF
scaricati in `pdf/`, nominati `anno_autori_titolo.pdf`. Impostazioni mostra
il percorso esatto e quanti file ci sono.

## LLM (facoltativo)

Un endpoint compatibile con l'API OpenAI — Ollama
(`http://localhost:11434/v1`), DeepSeek, OpenAI. Serve solo a
riorganizzare i termini in blocchi concettuali: senza, l'app costruisce i
blocchi dai soli dati e funziona lo stesso.

## Lingua e tema

L'interfaccia parte in inglese e si porta in italiano con i pulsanti
`IT` / `EN` in alto a destra. Accanto ci sono `chiaro`, `auto` e `scuro`:
`auto` segue il sistema. Entrambe le scelte restano memorizzate.

## Sviluppo

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest -q                     # 264 test, nessuno tocca la rete
.venv/bin/pytest -m rete tests/contratto  # controlla le API vere (CI settimanale)
.venv/bin/uvicorn ricerca.app:app --reload --port 8000
```

Un solo pacchetto Python: FastAPI rende HTML con Jinja2, htmx aggiorna i
frammenti di pagina. Niente Node, niente build, niente binari da firmare.

- `ricerca/keywords.py` — estrazione dei termini dalle banche dati
- `ricerca/strategy.py` — blocchi booleani e resa per motore
- `ricerca/sources/` — un modulo per motore, interfaccia unica
- `ricerca/search.py` — esecuzione parallela con isolamento degli errori
- `ricerca/history.py` — cronologia delle ricerche in JSON
- `ricerca/pdf.py` — scaricamento dei PDF ad accesso aperto
- `ricerca/export.py` — BibTeX, CSV e riferimenti APA
- `ricerca/finestra.py` — apertura in finestra propria
- `ricerca/macchina.py` — che cosa regge il computer, quale modello consigliare
- `ricerca/lavori.py` — operazioni che proseguono cambiando pagina
- `ricerca/registro.py` — registro delle attività e degli errori
- `ricerca/watchdog.py` — chiusura automatica quando la pagina si chiude
- `ricerca/cache.py` — cache SQLite delle risposte, come trasporto httpx
- `ricerca/zotero.py` — invio dei record inclusi a Zotero
- `ricerca/biblioteca.py` — testo dei PDF e ricerca a testo pieno
- `ricerca/i18n.py` — stringhe italiane e inglesi
- `docs/specs/` — il documento di progetto

---

# English

A literature search strategy assistant. From a topic it derives keywords,
controlled vocabulary terms and ready-made query strings for each database,
then runs the queries and exports the results.

## First launch

The first time it opens, a **guided setup** explains what each setting is for
and what changes if you leave it empty. It covers installing **Ollama**, which
models fit *this* machine (chosen by looking at memory and processor) with the
commands ready to copy — from the small **Gemma 4** builds for modest
machines up to **qwen3.8** where there is memory to spare — and the networked
alternatives: **DeepSeek** and **OpenAI**, with addresses, models and where to
get a key. You can skip it and
configure later; it can be reopened any time from Settings.

## How it works

1. **Topic** — write it in English or Italian.
2. **Suggested searches** — concepts from OpenAlex, MeSH terms from PubMed,
   terms recurring in the titles of the first results. These become editable
   boolean blocks and one query string per engine. No search runs until you
   start it.
3. **Results** — sources are queried in parallel, duplicates merged by DOI or
   title (even when one title is truncated or punctuated differently), the
   list ranked by relevance. Pick the fields, read it as a table or as **APA
   references**, download **open-access PDFs**, export to `.bib`, `.csv`, `.txt`.
4. **What each database did** — the query exactly as it was sent, how many
   records it returned, how many survived deduplication, how many **only it**
   found, and how long it took.
5. **Screening** — mark each record *include*, *maybe* or *exclude* with a
   reason, one at a time or **in bulk** on the ticked records — include, maybe,
   exclude, clear decisions, send to Zotero, download the open PDFs. Every row has
   its own **PDF** button: the article opens in a reader inside the app, with
   no trip to the system browser. The downloaded ones come out together as a
   **zip**, named after the citation key. The counters follow the PRISMA flow diagram and the
   **protocol** gathers strings, numbers and decisions for your Methods
   section, as Markdown or plain text.
6. **History** — every search is stored with its strategy and its records:
   reopen it, export it again, fetch its PDFs without running it twice.
7. **Library** — the downloaded PDFs are searchable in full text.

At the foot of every page there is a **log of what the app is doing**: one
line per database with the query sent, the records found and the time, and in
red whatever failed. Nothing fails silently: unexpected faults land there too,
and in `~/.ricerca/attivita.log`.

Searches and downloads **carry on server-side**: change page and come back, or
close the panel — the work does not stop, and a finished search shows up in
the history.

Year limits and “journal articles only” apply to every source, each in its own
syntax. Responses are cached locally for a day: refining a strategy does not
hammer the APIs.

Sources queried: OpenAlex, Crossref, PubMed, Europe PMC, arXiv, DOAJ, Semantic
Scholar (better with a key), CORE (free key), OPAC SBN for Italian books
(through the `opac-sbn-pp-cli` CLI, if installed). For Scopus and Web of Science the app
produces the string to paste into their own interface.

## Download and run

Grab the archive for your system from the
[Releases](https://github.com/nugh75/Ricerca-scientifica/releases) page,
extract it and start it:

| System | Archive | Start |
|---|---|---|
| macOS | `ricerca-*-macos.tar.gz` | drag **Ricerca.app** into Applications; first launch, right-click → *Open* |
| Windows | `ricerca-*-windows.zip` | double-click `avvia.bat` — `crea-scorciatoia-windows.bat` puts an icon on the Desktop |
| Linux | `ricerca-*-linux.tar.gz` | `./avvia.sh` — `installa-scorciatoia-linux.sh` adds it to the applications menu |

On macOS it is a real app bundle: it starts from its icon, **with no Terminal
window**. If macOS calls it “damaged” (which happens with unsigned downloaded
archives), run once:

```bash
xattr -dr com.apple.quarantine /Applications/Ricerca.app
```

**Closing the browser page quits the app** within about ten seconds: no
process left behind, no terminal needed to stop it. To keep it running:
`ricerca serve --resta-aperto`.

**Python is not required.** On first run the launcher downloads `uv` into the
app folder and lets it fetch the interpreter and the libraries: no admin
rights, no system changes, no `PATH` edits. Only an internet connection the
first time.

If the folder is read-only (say `/Applications` or `Program Files`), the
environment is created under `~/.ricerca` and the app folder is left
untouched.

**Upgrading**: download the new archive and start it. The launcher compares
the version with the installed one and rebuilds the environment when needed.

The running version is printed at the bottom of every page, and **Settings**
has *Which copy is running*: version, app folder, installed environment. If
the version does not change after an update, that panel says why — almost
always an old copy of the app is being opened. On macOS, delete the old
`Ricerca.app` before copying the new one, and empty the Trash. The first-run
log is at `~/.ricerca/avvio.log`.

Ricerca opens in **its own window**, with no address bar and no tabs: the
launcher looks for a Chromium-family browser (Chrome, Edge, Brave, Chromium,
Vivaldi) and starts it in app mode. If it finds none, it opens the default
browser; `ricerca serve --scheda` asks for a plain tab on purpose.

Safari has no such mode, but the window is one gesture away:
**Share → Add to Dock**. On Chrome and Edge, **Install app** in the address bar
does the same. Ricerca then sits among your applications, with its icon.

The server listens on `127.0.0.1` only.

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
sent back to the browser, and can be deleted with the *remove* checkbox. The
same folder holds the history and the PDFs in `pdf/`, named
`year_authors_title.pdf`; Settings shows the exact path and how many files are
there.

## LLM (optional)

Any endpoint compatible with the OpenAI API — Ollama
(`http://localhost:11434/v1`), DeepSeek, OpenAI. It only reorganises the terms
into conceptual blocks and translates an Italian topic before querying PubMed
(which finds no MeSH terms in Italian). Without it, blocks are built from the
data alone and everything else works the same.

## Configuration

Everything lives in `~/.ricerca/config.toml`, created by the app with `600`
permissions: courtesy email, LLM endpoint and model, Semantic Scholar, CORE,
NCBI and Zotero keys. No keyring, no system paths, no `sudo`. The same folder
holds the history (`cronologia.json`), the response cache (`cache.sqlite`) and
the downloaded PDFs (`pdf/`).

## Language and theme

The interface starts in English; the `IT` / `EN` buttons in the header switch
it to Italian. Next to them, `light`, `auto` and `dark`: `auto` follows the
system. Both choices are remembered.

## Development

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest -q                       # 264 tests, none touches the network
.venv/bin/pytest -m rete tests/contratto  # checks the real APIs (weekly in CI)
.venv/bin/uvicorn ricerca.app:app --reload --port 8000
```

One Python package: FastAPI renders HTML with Jinja2, htmx updates the
fragments. No Node, no build step, no binaries to sign.

- `ricerca/keywords.py` — pulls the terms out of the databases
- `ricerca/strategy.py` — boolean blocks and per-engine rendering
- `ricerca/sources/` — one module per engine, one interface
- `ricerca/search.py` — parallel execution, per-source error isolation
- `ricerca/history.py` — search history and screening decisions
- `ricerca/pdf.py`, `ricerca/biblioteca.py` — open-access PDFs and their text
- `ricerca/cache.py` — SQLite response cache, as an httpx transport
- `ricerca/zotero.py` — sends the included records to Zotero
- `ricerca/watchdog.py` — quits when the page is closed
- `ricerca/i18n.py` — Italian and English strings
- `docs/specs/` — the design document (Italian)

## Building the archives

```bash
./scripts/crea-release.sh      # they end up in dist/
```

In CI they are produced by `.github/workflows/release.yml` on every `v*` tag.
