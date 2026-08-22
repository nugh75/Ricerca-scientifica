# Ricerca

A literature search assistant. It turns a topic into keywords, ready-made
queries for every database, and a list of articles to screen — then keeps the
strategy, the numbers and the PDFs where you can find them again.

> **Version 2.4.** Stable: interfaces, file names and stored
> formats stay put, and what you save today opens tomorrow. Problems and
> suggestions: [open an issue](https://github.com/nugh75/Ricerca-scientifica/issues).

**English** · [Italiano](#italiano)

![Suggested searches](https://raw.githubusercontent.com/nugh75/Ricerca-scientifica/main/docs/screenshot/2-ricerche-suggerite.png)

## Download and run

Grab the archive for your system from the
[Releases](https://github.com/nugh75/Ricerca-scientifica/releases) page,
extract it and run the installer:

| System | Archive | How to start |
|---|---|---|
| macOS | `ricerca-*-macos.tar.gz` | double-click `install-or-update.command`; first launch, right-click Ricerca → *Open* if macOS asks |
| Windows | `ricerca-*-windows.zip` | double-click `install-or-update.bat` |
| Linux | `ricerca-*-linux.tar.gz` | run `./install-or-update.sh` |

**Python is not required.** On first run the launcher downloads `uv` into the
app folder and lets it fetch the interpreter and the libraries: no admin
rights, no system changes, no `PATH` edits. Only an internet connection the
first time.

Ricerca opens in **its own window**, without address bar or tabs: the launcher
looks for a Chromium-family browser (Chrome, Edge, Brave, Vivaldi) and starts
it in app mode. With Safari, *Share → Add to Dock* gives the same result; on
Chrome and Edge, *Install app* does. Closing the window quits the app, and
`ricerca serve --scheda` asks for a plain tab instead.

**Settings** chooses both: a window of its own or an ordinary browser tab, and
which browser to lean on among those found on the machine — or the system
default, which always opens a tab. The choice holds for the launcher too. For a
single launch, `--scheda` and `--browser` override it from the command line.

The server listens on `127.0.0.1` only: it is never reachable from another
machine.

**Upgrading**: download the new archive and run the same installer. It replaces
the installed application, keeps one previous copy for recovery, refreshes the
shortcut, and starts the new version. Searches, review workspaces, settings and
PDFs stay under `~/.ricerca` (or the equivalent user folder on Windows) and are
never moved. The running version is printed at the foot of every page; Settings
shows which copy is running, and from which folder.

## First launch

A guided setup explains every setting: what it is for, what changes if you fill
it in, what happens if you leave it empty. It covers installing **Ollama**,
which models fit *this* machine — memory and processor are detected, so the
advice runs from the small Gemma 4 builds up to qwen3.8 where there is room —
and the networked alternatives, **DeepSeek** and **OpenAI**, with addresses,
models, costs and where to get a key. Nothing is required: you can skip it and
configure later, and reopen it any time from Settings.

## How it works

### Review workspaces (current source)

- A review project combines multiple saved searches and citation-chasing runs
  into one stable, deduplicated corpus while retaining every provenance and
  exact query.
- The method runs as an actual sequence: versioned PICO/PICOS/PCC protocol,
  PRISMA-S/PRESS and sentinel-article checks, blinded title/abstract and
  full-text screening, conflict resolution, full-text retrieval, study/report
  linking, independent extraction, critical appraisal, GRADE-style Summary of
  findings, and living-review updates.
- A dedicated **LLM Wiki Graph** compiles every corpus record into a source
  page and connects articles, authors, and venues from certain metadata. When
  an LLM is configured, it adds concept pages and relations from included
  abstracts; unknown source IDs and quotations absent from those abstracts are
  rejected locally. The graph remains useful without an LLM.
- Assisted screening only changes reading order. It explains its score from
  terms in prior human decisions, never excludes a record, and leaves the
  corpus order untouched. Complete Markdown and JSON exports preserve the
  audit trail.

### New in 2.4.0

- On the reviews page the form for a new review sits in the page flow, under
  the list of projects, instead of in a panel pinned to the right.

### New in 2.3.0

- Settings chooses how the app opens: a window of its own, without address bar
  or tabs, or an ordinary browser tab like any other site.
- It also chooses which browser to lean on, among those found on the machine —
  listed by name, not by executable — or the system default, which always opens
  a tab. Only Chromium-family browsers can give a window of its own, so picking
  the default switches to a tab rather than failing to open.
- The choice lives in the configuration, so it holds for the launcher too, which
  starts the app without options. `--scheda` and the new `--browser` override it
  for a single launch.
- A browser chosen and later uninstalled no longer stands in the way: the app
  goes back to looking on its own, and Settings still shows what had been picked.

### New in 2.2.0

- Every record carries a free note: what this article is for, which page to
  reread, what does not add up. It stays with the record, can be shown as a
  column and travels into the CSV.
- A review corpus now follows the searches it came from. A name fixed by hand
  or a field filled in by Unpaywall reaches the project instead of stopping at
  the photograph taken on the day of linking.
- It does not follow them silently: every departure from the linked version is
  recorded with the previous value and the date, readable on the record under
  **Metadata changed** and written into the Markdown export. A review must be
  able to say what changed and when.
- The note is shared and written from both sides — from the record card and
  from the screening card. It is the same note wherever it is touched.
- A retraction is never undone by the alignment, and if the original search has
  been deleted the corpus still stands on the copy it kept.

### New in 2.1.0

- Deleting asks first. Clearing the history or removing a saved search wants a
  confirmation; a review project — protocol, screening, extractions and
  synthesis — is deleted only by typing its title back.
- A screening decision inside a review swaps that record alone, and the counts
  update around it. «i», «f», «e» and the arrows work there too. Without
  JavaScript the whole page still comes back, as before.
- The library opens the PDF it found the phrase in, in the reader inside the app.
- Results take the address of the saved search: reloading no longer loses them,
  and the last five searches sit on the front page.
- The history is filtered by topic and split into pages.
- A saved search reopens ready to run again, filters included.
- A single record joins a review without linking the whole search, and a review
  project can be renamed once the work has settled its title.
- Extraction and critical appraisal are split into pages.

### New in 2.0.0

- First stable release. The name of every stored file and the shape of every
  saved format are now fixed: what this version writes, later versions read.
- Screening a record swaps that record alone. The keyboard flow survives the
  decision, so «i», «f», «e» and the arrows keep working down a long list
  instead of dying after the first click.
- The reason field opens when there is a decision to explain, and stays out of
  the way on the rows that have none.
- The search strings are shown right above **Run the search**, and they follow
  the blocks as they are edited: no button to remember, and nothing is sent
  before it has been read. Niche OpenAlex filters start folded.
- The closing stages of a review — extraction, appraisal, synthesis, wiki,
  updates — arrive when they come into view, so opening a large project no
  longer means building thousands of fields nobody is looking at.
- A filter that matches nothing now offers the way back out.

### New in 1.0.0b7

- Review workspaces now cover the whole evidence-synthesis workflow: versioned
  protocol, reproducible multi-search corpus, blinded dual screening,
  full-text retrieval, independent extraction and consensus, critical
  appraisal, GRADE-style evidence tables, and explicit living updates.
- A navigable literature wiki and interactive graph are generated from corpus
  metadata and abstracts. LLM concepts keep source IDs and locally validated
  evidence; metadata-only generation remains available offline.
- The review stage rail, paginated conflict-first screening, resizable fields,
  contextual actions, and dedicated wiki page keep long projects readable on
  desktop and mobile.

### New in 1.0.0b6

- Saved searches now use three focused workspaces: **Results**, **Field
  profile**, and **Protocol**. Page hierarchy, menus, icons, preferences, and
  notifications have been simplified, while redundant step numbering has
  been removed.
- A compact PRISMA rail shows screening progress and filters records by status.
  Bulk decisions, downloads, metadata completion, and Zotero export now require
  an explicit selection or an explicit choice to act on every saved record.
- Keyword suggestions remain visible beside resizable Boolean-block fields;
  screening reasons use full-width, multiline boxes. Author and journal
  profiles can reveal the articles citing each most-cited work and return to
  the originating Explore page with one control.

### New in 1.0.0b5

- Every search now separates the operational **Results** from the reproducible
  **Protocol** in two keyboard-accessible tabs. Compact controls use local SVG
  icons with full tooltips, while notifications no longer carry a heavy
  vertical rule.
- Citation counts are shown by default in results and CSV exports, including a
  real zero. OpenAlex author and journal identities are retained through
  history and deduplication, so names link to the right entity; older records
  without an ID open a name search instead of guessing.
- **Explore** adds searchable author and journal pages with OpenAlex identity,
  output, citations, h-index, i10-index, yearly trend and most-cited works.
  Counts are labelled as an OpenAlex snapshot and should not be read as a
  stand-alone measure of research quality.

### New in 1.0.0b4

- Saved results can now be filtered across the complete search, before the
  50-record pagination, by title, author, venue or DOI, year range, source and
  screening status.
- Text matching is case- and accent-insensitive. Filtered rows keep their
  original history index, so record cards, screening and PDF actions always
  operate on the intended work.
- Filters remain active while changing page or view and after bulk actions;
  changing a screening decision also refreshes a status-filtered list.

### New in 1.0.0b3

- Citation chasing now resolves PubMed, Europe PMC and Crossref records in
  OpenAlex by DOI. When a DOI is unavailable, title and year must provide a
  strong match before any related records are shown.
- Related works use a screening-oriented layout: selection starts at the left
  edge, abstracts expand in place, and available copies and article pages open
  before a record is added to the search. Selected works remain in the search
  history.
- Abstracts already stored with visible JATS or HTML tags are cleaned when the
  history is read.

### New in 1.0.0b2

- OpenAlex records now include reconstructed abstracts, retraction status,
  citation counts, top-10%-cited markers and archive availability. The card
  can chase references backwards, citing works forwards and related works
  sideways, adding only the records you choose to the end of the search.
- OpenAlex-only filters cover language, retractions, open access, archive PDF,
  journal, institution and funder. There is also an optional meaning-based
  source, term autocomplete, a reproducible random sample and cursor paging up
  to 200 records.
- The field profile groups the complete OpenAlex result set by year, document
  type, open access, topic and author country. The protocol retains filters and
  OpenAlex OQL, while Settings shows the credit spent and left for the day.
- After declared open links and Unpaywall have failed, an explicitly enabled
  option can try the OpenAlex PDF archive. It requires a key, costs $0.01 per
  file and does not change the work's original copyright.

1. **Topic** — write it in English or Italian.
2. **Suggested searches** — concepts and keywords from OpenAlex, MeSH terms
   from PubMed, terms recurring in the titles of the first results. These
   become editable boolean blocks and one query string per engine. Year limits
   and “journal articles only” apply to every source, each in its own syntax.
   No search runs until you start it.
3. **Results** — sources are queried in parallel, duplicates merged by DOI or
   title (even when one title is truncated or punctuated differently), the list
   ranked by relevance. A panel shows **what each database did**: the query as
   it was sent, records found, how many survived deduplication, how many only
   it found, and how long it took.
   Clicking a title opens the **record card**: all the authors, the whole
   abstract, which databases found it, the file on disk, the APA and BibTeX
   citation ready to copy, and the link to the publisher. Metadata that arrived
   wrong can be **corrected by hand** there — the original stays in the history,
   the exports use the corrected version. From the card you can also ask the
   model for a **five-part summary** — aims, method, results, discussion,
   conclusion, in English or Italian — built on the text of the PDF when there
   is one, otherwise on the abstract; it stays saved with the record.
4. **Screening** — mark each record *include*, *maybe* or *exclude* with a
   reason, one at a time or in bulk on the ticked records. Counters follow the
   PRISMA flow; the protocol export gathers strings, numbers and decisions for
   your Methods section, as Markdown or plain text.
5. **PDFs** — each record carries **every link the sources declare** — OpenAlex
   keeps them in three different fields, Europe PMC in its full-text list,
   PubMed as a PubMed Central copy, Crossref as publisher links — and the
   download tries them in turn until one returns a real PDF, because the first
   is often a landing page. **Unpaywall** fills in what the databases left out
   (venue, year, authors) and steps in automatically when every link fails: it
   knows the repository copies publishers do not declare. Measured on real
   searches: trying every link took one search from no PDF at all to eleven;
   on a sample of twenty-seven records where every link had failed, Unpaywall
   opened two more, and on another of six it found nothing — those were closed
   for good. That is where manual upload comes in: when a publisher blocks
   automated downloads — common, and it does not block people — the card lets
   you **upload the PDF you fetched with your institutional credentials**, and
   it joins the others in the full-text search and the summary. Open articles
   download with one button, per row or all at once, and open in a reader
   **inside the app**. Files are named `year_authors_title.pdf`; the whole set
   comes out as a zip.
6. **History** — every search is stored with its strategy and its records:
   reopen it, export it again, fetch its PDFs without running it twice.
7. **Library** — the downloaded PDFs are searchable in full text.

Exports: `.bib`, `.csv` with the fields you choose, APA 7 references, and the
search protocol.

The list is paged at fifty records, rows can be screened from the keyboard
(`i`, `f`, `e`, arrows to move), and the layout follows the screen: on a phone
each record becomes a card, on a wide monitor the tables use the room. `roomy`
/ `compact` in the header changes the density; both stay remembered.

Failures never rearrange the page: they arrive as a notice in the corner,
which stays until dismissed, while the list underneath is left untouched. At
the foot of every page there is a **log of what the app is doing**: one line
per database with the query sent, the records found and the time, and in red
whatever failed. Nothing fails silently — unexpected faults land there too, and
in `~/.ricerca/activity.log`. Searches and downloads **carry on server-side**:
change page and come back, the work does not stop.

Sources queried: OpenAlex (keyword and optional meaning-based search),
Crossref, PubMed, Europe PMC, arXiv, DOAJ, Semantic Scholar, CORE, and OPAC SBN
for Italian books. For Scopus and Web of Science the app produces the string
to paste into their own interface.

## Keys and email: all from the interface

No key is required, and none has to be written into a file by hand. From
**Settings** (or the guided setup) you can set:

- the **courtesy email**, which OpenAlex, Crossref and Unpaywall use to know
  who is calling — Unpaywall does not answer without it;
- the free **OpenAlex key** — without it you are in the anonymous lane, which
  has a daily budget and then answers `429`. It takes a minute to request at
  [openalex.org/rest-api](https://openalex.org/rest-api) and it is the single
  field that most improves the suggestions;
- **Semantic Scholar**, **CORE** and **NCBI** keys;
- **Zotero** key and library, to send the selected records with one button;
- an optional **LLM endpoint and model**.

Keys live in `~/.ricerca/config.toml` with `600` permissions, are never sent
back to the browser, and are deleted with the *remove* checkbox. The same folder
holds the history, the response cache and the PDFs; Settings shows the exact
paths.

## LLM (optional)

Any endpoint compatible with the OpenAI API — Ollama
(`http://localhost:11434/v1`), DeepSeek, OpenAI. It does three things: reorganise the
terms into conceptual blocks, translate an Italian topic into English before
querying PubMed (which finds no MeSH terms in Italian), and summarise an
article in five parts from the record card. Without it, blocks
are built from the data alone and everything else works the same. With Ollama
nothing leaves your computer; with a networked service, the topic and the terms
are sent to it.

## Language and theme

The interface starts in English; the `IT` / `EN` buttons in the header switch it
to Italian. Next to them, `light`, `auto` and `dark`. Both choices are
remembered.

## Development

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest -q                       # 471 tests, none touches the network
.venv/bin/pytest -m rete tests/contratto  # checks the real APIs (weekly in CI)
.venv/bin/uvicorn ricerca.app:app --reload --port 8000
```

One Python package: FastAPI renders HTML with Jinja2, htmx updates the
fragments. No Node, no build step, no binaries to sign.

| File | What it holds |
|---|---|
| `ricerca/keywords.py` | pulls the terms out of the databases |
| `ricerca/openalex_api.py`, `costo.py` | the single OpenAlex gateway and its daily credit ledger |
| `ricerca/citazioni.py`, `faccette.py` | citation chasing and the OpenAlex field profile |
| `ricerca/strategy.py` | boolean blocks and per-engine rendering |
| `ricerca/sources/` | one module per engine, one interface |
| `ricerca/search.py` | parallel execution, per-source error isolation |
| `ricerca/lavori.py` | work that carries on when you change page |
| `ricerca/registro.py` | the activity and error log |
| `ricerca/history.py` | search history and screening decisions |
| `ricerca/pdf.py`, `biblioteca.py` | open-access PDFs and their text |
| `ricerca/cache.py` | SQLite response cache, as an httpx transport |
| `ricerca/unpaywall.py` | missing metadata and open copies, from the DOI |
| `ricerca/llm.py` | blocks, translation, summaries, grounded wiki concepts |
| `ricerca/revisioni.py`, `ricerca/wiki.py` | review workflow, literature wiki and graph |
| `ricerca/zotero.py` | sends the included records to Zotero |
| `ricerca/macchina.py` | what the computer can run, which model to suggest |
| `ricerca/finestra.py`, `watchdog.py` | its own window; quits when closed |
| `ricerca/i18n.py` | Italian and English strings |
| `docs/specs/` | the design document (Italian) |

## Licence

GNU General Public License, version 3 or later — the full text is in
[`LICENSE`](LICENSE). You may use, study, change and redistribute it; a
modified copy you pass on must stay free under the same licence and carry its
source.

Building the archives: `./scripts/crea-release.sh` (they end up in `dist/`); in
CI, `.github/workflows/release.yml` on every `v*` tag. The archives carry the
source and the launcher only — around 200 KB; the screenshots stay here, where
they are read.

---

# Italiano

> **Versione 2.4.** Stabile: interfaccia, nomi dei file e
> formati salvati restano al loro posto, e quello che salvi oggi si riapre
> domani. Problemi e proposte:
> [apri una segnalazione](https://github.com/nugh75/Ricerca-scientifica/issues).

Assistente di ricerca bibliografica. Trasforma un argomento in parole chiave,
stringhe di ricerca pronte per ogni banca dati e un elenco di articoli da
selezionare — e poi tiene strategia, numeri e PDF dove si ritrovano.

## Scarica e avvia

Dalla pagina [Releases](https://github.com/nugh75/Ricerca-scientifica/releases)
scarica l'archivio del tuo sistema, estrailo e avvia l'installatore:

| Sistema | Archivio | Avvio |
|---|---|---|
| macOS | `ricerca-*-macos.tar.gz` | doppio clic su `install-or-update.command`; al primo avvio clic destro su Ricerca → *Apri* se macOS lo richiede |
| Windows | `ricerca-*-windows.zip` | doppio clic su `install-or-update.bat` |
| Linux | `ricerca-*-linux.tar.gz` | esegui `./install-or-update.sh` |

**Non serve installare Python.** Al primo avvio il lanciatore scarica `uv`
nella cartella dell'app e con esso l'interprete e le librerie: nessun permesso
di amministratore, nessuna modifica al sistema, nessun `PATH` da sistemare.
Serve solo una connessione a internet la prima volta.

Ricerca si apre in una **finestra propria**, senza barra degli indirizzi né
schede: il lanciatore cerca un browser della famiglia Chromium e lo avvia in
modo applicazione. Con Safari lo stesso risultato si ottiene da *Condividi →
Aggiungi al Dock*; su Chrome ed Edge da *Installa applicazione*. Chiudendo la
finestra l'app si chiude, e `ricerca serve --scheda` chiede apposta una scheda.

In **Impostazioni** si sceglie tutto e due: finestra propria o normale scheda
del browser, e su quale browser appoggiarsi fra quelli trovati sulla macchina —
oppure quello predefinito di sistema, che apre sempre una scheda. La scelta vale
anche per il lanciatore. Per un avvio soltanto, `--scheda` e `--browser` la
scavalcano dalla riga di comando.

Il server ascolta solo su `127.0.0.1`: non è raggiungibile da altre macchine.

**Aggiornare**: scarica il nuovo archivio e avvia lo stesso installatore.
Sostituisce automaticamente l'app installata, conserva una sola copia
precedente per il ripristino, aggiorna il collegamento e apre la versione nuova.
Ricerche, workspace di review, impostazioni e PDF restano in `~/.ricerca` (o
nella cartella utente equivalente su Windows) e non vengono spostati. La
versione in esecuzione è scritta in fondo a ogni pagina; Impostazioni dice
quale copia sta girando, e da quale cartella.

## Prima apertura

Una configurazione guidata spiega ogni impostazione: a che serve, che cosa
cambia se la compili, che cosa succede se la lasci vuota. C'è come installare
**Ollama**, quali modelli reggono *questa* macchina — memoria e processore
vengono rilevati, e il consiglio va dai tagli piccoli di Gemma 4 fino a
qwen3.8 dove c'è spazio — e le alternative in rete, **DeepSeek** e **OpenAI**,
con indirizzi, modelli, costi e dove si prende la chiave. Niente è
obbligatorio: si può saltare e configurare dopo, e rivedere la guida quando si
vuole da Impostazioni.

## Come funziona

### Workspace di review (sorgente attuale)

- Un progetto riunisce più ricerche salvate e attività di snowballing in un
  corpus stabile e deduplicato, conservando ogni provenienza e stringa esatta.
- Il metodo diventa una sequenza reale: protocollo PICO/PICOS/PCC versionato,
  controlli PRISMA-S/PRESS e articoli sentinella, screening cieco di
  titolo/abstract e testo completo, risoluzione dei conflitti, reperimento dei
  full text, collegamento studio–report, estrazione indipendente, valutazione
  critica, Summary of findings in stile GRADE e aggiornamenti living.
- Una **LLM Wiki Graph** dedicata compila ogni record del corpus in una
  pagina-fonte e collega articoli, autori e riviste tramite metadati certi. Se
  è configurato un LLM, aggiunge pagine concettuali e relazioni dagli abstract
  inclusi; ID fonte sconosciuti e citazioni assenti dagli abstract vengono
  scartati localmente. Il grafo resta utile anche senza LLM.
- Lo screening assistito cambia soltanto l'ordine di lettura: spiega il
  punteggio tramite i termini delle precedenti decisioni umane, non esclude mai
  un record e non altera l'ordine del corpus. Gli export Markdown e JSON
  conservano l'intero audit trail.

### Novità in 2.4.0

- Nella pagina delle review il modulo per crearne una nuova sta nel flusso
  della pagina, sotto l'elenco dei progetti, invece che in un pannello
  ancorato a destra.

### Novità in 2.3.0

- In Impostazioni si sceglie come si apre l'app: in una finestra propria, senza
  barra degli indirizzi né schede, oppure in una normale scheda del browser,
  come un sito qualsiasi.
- Si sceglie anche su quale browser appoggiarsi, fra quelli trovati sulla
  macchina — elencati per nome, non per eseguibile — oppure quello predefinito
  di sistema, che apre sempre una scheda. La finestra propria la sanno dare solo
  i browser della famiglia Chromium: scegliendo il predefinito si passa alla
  scheda invece di non aprire niente.
- La scelta vive nella configurazione, quindi vale anche per il lanciatore, che
  avvia l'app senza opzioni. `--scheda` e il nuovo `--browser` la scavalcano per
  un avvio soltanto.
- Un browser scelto e poi disinstallato non blocca più l'avvio: si torna a
  cercare, e Impostazioni continua a mostrare che cosa era stato scelto.

### Novità in 2.2.0

- Ogni record porta un appunto libero: a che cosa serve questo articolo, quale
  pagina rileggere, che cosa non torna. Sta con il record, si può mostrare come
  colonna e finisce nel CSV.
- Il corpus di una review segue ora le ricerche da cui viene. Un nome sistemato
  a mano o un campo completato da Unpaywall arriva nel progetto, invece di
  fermarsi alla fotografia del giorno del collegamento.
- Non le segue in silenzio: ogni scostamento dalla versione collegata viene
  registrato con il valore di prima e la data, si legge sul record sotto
  **Metadati cambiati** ed entra nell'export Markdown. Una revisione deve poter
  dire che cosa è cambiato e quando.
- L'appunto è condiviso e si scrive dai due lati — dalla scheda del record e da
  quella dello screening. È lo stesso appunto ovunque lo si tocchi.
- Un ritiro non viene mai annullato dall'allineamento, e se la ricerca d'origine
  è stata cancellata il corpus regge sulla copia che ha conservato.

### Novità in 2.1.0

- Le cancellazioni chiedono. Svuotare la cronologia o togliere una ricerca
  salvata vuole una conferma; un progetto di review — protocollo, screening,
  estrazioni e sintesi — si cancella soltanto riscrivendone il titolo.
- Una decisione di screening dentro una review scambia quel record soltanto, e
  i conteggi si aggiornano attorno. Anche lì valgono «i», «f», «e» e le frecce.
  Senza JavaScript torna la pagina intera, come prima.
- La biblioteca apre il PDF in cui ha trovato la frase, nel lettore dentro l'app.
- I risultati prendono l'indirizzo della ricerca salvata: ricaricare non li
  perde più, e le ultime cinque stanno in prima pagina.
- La cronologia si filtra per argomento e si divide in pagine.
- Una ricerca salvata si riapre pronta da rilanciare, filtri compresi.
- Un singolo record entra in una review senza collegare tutta la ricerca, e un
  progetto di review si può rinominare quando il lavoro ne ha assestato il
  titolo.
- Estrazione e valutazione critica si dividono in pagine.

### Novità in 2.0.0

- Prima release stabile. I nomi dei file salvati e la forma dei formati sono
  fermi: quello che scrive questa versione, le prossime lo rileggono.
- Valutare un record scambia quel record soltanto. Il lavoro da tastiera
  sopravvive alla decisione: «i», «f», «e» e le frecce continuano a funzionare
  lungo tutto l'elenco invece di spegnersi al primo clic.
- Il campo del motivo si apre quando c'è una decisione da spiegare e resta
  chiuso sulle righe che non ne hanno.
- Le stringhe di ricerca stanno appena sopra **Avvia la ricerca** e seguono i
  blocchi mentre li si modifica: nessun bottone da ricordare, e niente parte
  prima di essere stato letto. I filtri OpenAlex di nicchia partono chiusi.
- Le fasi finali di una review — estrazione, valutazione, sintesi, wiki,
  aggiornamenti — arrivano quando si guardano: aprire un progetto grande non
  significa più costruire migliaia di campi che nessuno sta leggendo.
- Un filtro che non trova nulla propone l'uscita.

### Novità in 1.0.0b7

- I workspace di review coprono l'intero flusso di sintesi delle evidenze:
  protocollo versionato, corpus riproducibile da più ricerche, doppio screening
  cieco, reperimento dei full text, estrazione indipendente e consenso,
  valutazione critica, tabelle GRADE e aggiornamenti espliciti.
- Una wiki navigabile e un grafo interattivo della letteratura sono generati da
  metadati e abstract. I concetti LLM conservano ID fonte ed evidenze validate
  localmente; la generazione dai soli metadati funziona anche offline.
- La traccia delle fasi, lo screening paginato con conflitti in testa, i campi
  ridimensionabili, le azioni contestuali e la pagina wiki dedicata mantengono
  leggibili anche i progetti lunghi su desktop e mobile.

### Novità in 1.0.0b6

- Le ricerche salvate usano tre spazi distinti: **Risultati**, **Profilo del
  campo** e **Protocollo**. Gerarchia delle pagine, menu, icone, preferenze e
  notifiche sono più semplici; le numerazioni di percorso ridondanti sono state
  eliminate.
- Una barra PRISMA compatta mostra l'avanzamento dello screening e filtra i
  record per stato. Decisioni, PDF, completamento dei metadati e invio a Zotero
  in blocco richiedono una selezione oppure la scelta esplicita di tutti i
  record salvati.
- I suggerimenti di parole chiave restano visibili accanto ai campi
  ridimensionabili dei blocchi booleani; le motivazioni di screening usano box
  multilinea a larghezza piena. Nei profili di autori e riviste si possono
  caricare gli articoli citanti e tornare con un comando alla pagina Esplora di
  provenienza.

### Novità in 1.0.0b5

- Ogni ricerca separa ora i **Risultati** operativi dal **Protocollo**
  riproducibile in due tab accessibili anche da tastiera. I controlli compatti
  usano icone SVG locali con tooltip completi; le notifiche non hanno più una
  pesante barra verticale.
- Le citazioni compaiono per impostazione predefinita nei risultati e nel CSV,
  compreso lo zero reale. Le identità OpenAlex di autori e riviste restano in
  cronologia e nella deduplica, quindi i nomi portano all'entità corretta; i
  vecchi record senza ID aprono una ricerca per nome, senza indovinare.
- **Esplora** aggiunge pagine ricercabili per autori e riviste con identità
  OpenAlex, produzione, citazioni, indice h, indice i10, andamento annuale e
  lavori più citati. I conteggi sono dichiarati come fotografia OpenAlex e non
  come misura autonoma della qualità della ricerca.

### Novità in 1.0.0b4

- I risultati salvati si possono ora filtrare sull'intera ricerca, prima della
  paginazione a 50 record, per titolo, autore, sede o DOI, intervallo di anni,
  fonte e stato di screening.
- La ricerca testuale non distingue maiuscole o accenti. Le righe filtrate
  conservano l'indice originale nella cronologia, quindi scheda, screening e
  azioni PDF operano sempre sul lavoro corretto.
- I filtri restano attivi cambiando pagina o vista e dopo le azioni di massa;
  una decisione di screening aggiorna anche un elenco filtrato per stato.

### Novità in 1.0.0b3

- Lo snowballing risolve ora in OpenAlex anche i record provenienti da PubMed,
  Europe PMC e Crossref tramite DOI. In assenza del DOI, titolo e anno devono
  produrre una corrispondenza forte prima di mostrare lavori collegati.
- I lavori collegati adottano una vista orientata allo screening: la selezione
  parte dal margine sinistro, l'abstract si espande nella lista e la copia
  disponibile o la pagina dell'articolo si aprono prima di aggiungere il record
  alla ricerca. I lavori scelti restano nella cronologia.
- Gli abstract già salvati con tag JATS o HTML visibili vengono ripuliti durante
  la lettura della cronologia.

### Novità in 1.0.0b2

- I record OpenAlex portano abstract ricostruito, stato di ritiro, numero di
  citazioni, indicatore del 10% più citato e disponibilità nell'archivio. Dalla
  scheda si inseguono bibliografia, lavori citanti e lavori vicini, aggiungendo
  in coda solo quelli scelti.
- I filtri solo OpenAlex coprono lingua, ritiri, accesso aperto, PDF in
  archivio, rivista, ateneo e finanziatore. Si aggiungono una fonte semantica
  facoltativa, l'autocomplete dei termini, il campione casuale riproducibile e
  la paginazione a cursore fino a 200 record.
- Il profilo del campo raggruppa l'intero risultato OpenAlex per anno, tipo,
  accesso aperto, tema e paese degli autori. Il protocollo conserva filtri e
  OQL; Impostazioni mostra il credito giornaliero speso e quello rimasto.
- Dopo il fallimento dei link aperti e di Unpaywall, un'opzione da accendere a
  mano può provare l'archivio PDF OpenAlex. Richiede la chiave, costa $0.01 a
  file e non cambia il copyright originale del lavoro.

1. **Argomento** — in italiano o in inglese.
2. **Ricerche suggerite** — concetti e parole chiave da OpenAlex, termini MeSH
   da PubMed, termini che ricorrono nei titoli dei primi risultati. Da questi
   nascono i blocchi booleani, modificabili, e le stringhe per ogni motore.
   Limiti di anno e «solo articoli di rivista» valgono per tutte le fonti,
   ognuna con la sua sintassi. Nessuna ricerca parte finché non la avvii tu.
3. **Risultati** — fonti interrogate in parallelo, duplicati uniti per DOI o
   titolo (anche quando un titolo è troncato o punteggiato diversamente),
   elenco ordinato per pertinenza. Un pannello mostra **che cosa ha fatto ogni
   banca dati**: la stringa come è stata inviata, i record trovati, quanti ne
   restano dopo la deduplica, quanti li ha trovati solo lei, in quanto tempo.
   Un clic sul titolo apre la **scheda del record**: tutti gli autori,
   l'abstract intero, da quali banche dati arriva, il file su disco, la
   citazione APA e BibTeX pronte da copiare, il collegamento all'editore. I
   metadati arrivati storti si **correggono a mano** lì: l'originale resta nella
   cronologia, negli export va la versione corretta. Dalla scheda si chiede
   anche al modello un **riassunto in cinque parti** — obiettivi, metodo,
   risultati, discussione, conclusione, in italiano o in inglese — costruito sul
   testo del PDF quando c'è, altrimenti sull'abstract; resta salvato col record.
4. **Selezione** — ogni record si marca *incluso*, *forse* o *escluso* con un
   motivo, uno per volta o in blocco sui record spuntati. I conteggi seguono il
   diagramma PRISMA; il protocollo raccoglie stringhe, numeri e decisioni per
   la sezione «Metodo», in Markdown o in testo semplice.
5. **PDF** — ogni record porta con sé **tutti i collegamenti che le fonti
   dichiarano** — OpenAlex li tiene in tre campi diversi, Europe PMC nel suo
   elenco di testi pieni, PubMed come copia in PubMed Central, Crossref come
   collegamenti dell'editore — e lo scaricamento li prova a turno finché uno
   restituisce un PDF vero, perché il primo è spesso una pagina di
   destinazione. **Unpaywall** completa quello che le banche dati hanno
   lasciato fuori (sede, anno, autori) e interviene da solo quando tutti i
   collegamenti falliscono: conosce le copie nei depositi che gli editori non
   dichiarano. Misurato su ricerche vere: provare tutti i collegamenti ha
   portato una ricerca da nessun PDF a undici; su un campione di ventisette
   record in cui ogni collegamento era fallito Unpaywall ne ha aperti altri
   due, e su un altro di sei non ha trovato nulla — quelli erano chiusi
   davvero. È lì che serve il caricamento a mano: quando un editore blocca gli
   scaricamenti automatici — capita spesso, e non blocca le persone — dalla
   scheda si **carica il PDF preso con le credenziali del proprio ateneo**, ed
   entra con gli altri nella ricerca a testo pieno e nel riassunto. Gli
   articoli aperti si scaricano con un tasto, per riga o tutti insieme, e si
   leggono in un lettore **dentro l'app**. I file si chiamano
   `anno_autori_titolo.pdf`; l'insieme esce in uno zip.
6. **Cronologia** — ogni ricerca resta con la sua strategia e i suoi record: si
   riapre, si riesporta, se ne scaricano i PDF senza ripeterla.
7. **Biblioteca** — i PDF scaricati sono cercabili a testo pieno.

Export: `.bib`, `.csv` con i campi che scegli, riferimenti APA 7 e il
protocollo di ricerca.

L'elenco è diviso in pagine da cinquanta record, lo screening si fa anche da
tastiera (`i`, `f`, `e`, frecce per spostarsi) e l'impaginato segue lo schermo:
sul telefono ogni record diventa una scheda, su un monitor largo le tabelle
usano lo spazio. In testata `comoda` / `compatta` cambia la densità; entrambe
le scelte restano memorizzate.

Gli errori non scompaginano la pagina: arrivano come avviso in un angolo, che
resta finché non lo si chiude, mentre l'elenco sotto non viene toccato. In
fondo a ogni pagina c'è **il registro di quel che l'app sta facendo**: una
riga per banca dati con la stringa inviata, i record trovati e il tempo, in
rosso ciò che non ha funzionato. Nessun errore resta muto: anche i guasti
imprevisti finiscono lì e in `~/.ricerca/activity.log`. Ricerche e scaricamenti
**proseguono sul server**: si può cambiare pagina e tornare, il lavoro non si
ferma.

Motori interrogati: OpenAlex (per parole e, facoltativamente, per
significato), Crossref, PubMed, Europe PMC, arXiv, DOAJ, Semantic Scholar, CORE
e OPAC SBN per i libri italiani. Per Scopus e Web of Science l'app produce la
stringa da incollare nella loro interfaccia.

## Chiavi ed email: tutto dall'interfaccia

Nessuna chiave è obbligatoria e nessuna va scritta a mano in un file. Da
**Impostazioni** (o dalla guida iniziale) si impostano:

- l'**email di cortesia**, che OpenAlex, Crossref e Unpaywall usano per
  riconoscere chi interroga — senza, Unpaywall non risponde affatto;
- la **chiave OpenAlex**, gratuita: senza si resta nella corsia anonima, che ha
  un budget giornaliero e poi risponde `429`. Si richiede in un minuto su
  [openalex.org/rest-api](https://openalex.org/rest-api) ed è il singolo campo
  che più migliora i suggerimenti;
- le chiavi **Semantic Scholar**, **CORE** e **NCBI**;
- chiave e libreria **Zotero**, per spedire i record scelti con un tasto;
- endpoint e modello **LLM**, facoltativi.

Le chiavi restano in `~/.ricerca/config.toml` con permessi `600`, non vengono
mai rimandate al browser e si cancellano con la spunta *rimuovi*. Nella stessa
cartella stanno cronologia, cache delle risposte e PDF; Impostazioni mostra i
percorsi esatti.

## LLM (facoltativo)

Qualsiasi endpoint compatibile con l'API OpenAI — Ollama
(`http://localhost:11434/v1`), DeepSeek, OpenAI. Fa tre cose: riorganizza i termini
in blocchi concettuali, traduce in inglese un argomento italiano prima di
interrogare PubMed (che in italiano non trova i MeSH) e riassume un articolo in
cinque parti dalla scheda del record. Senza, i blocchi si
costruiscono dai soli dati e tutto il resto funziona identico. Con Ollama non
esce nulla dal computer; con un servizio in rete, argomento e termini vengono
inviati a quel servizio.

## Lingua e tema

L'interfaccia parte in inglese e si porta in italiano con i pulsanti `IT` /
`EN` in alto a destra. Accanto, `chiaro`, `auto` e `scuro`. Entrambe le scelte
restano memorizzate.

## Sviluppo

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest -q                       # 471 test, nessuno tocca la rete
.venv/bin/pytest -m rete tests/contratto  # controlla le API vere (CI settimanale)
.venv/bin/uvicorn ricerca.app:app --reload --port 8000
```

Un solo pacchetto Python: FastAPI rende HTML con Jinja2, htmx aggiorna i
frammenti. Niente Node, niente build, niente binari da firmare. La mappa dei
file è nella tabella della sezione inglese; il documento di progetto sta in
`docs/specs/`.

## Licenza

GNU General Public License, versione 3 o successiva — il testo completo è in
[`LICENSE`](LICENSE). Si può usare, studiare, modificare e ridistribuire; una
copia modificata che si passa ad altri resta libera alla stessa licenza e va
accompagnata dal sorgente.
