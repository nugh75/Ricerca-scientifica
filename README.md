# Ricerca

A literature search assistant. It turns a topic into keywords, ready-made
queries for every database, and a list of articles to screen — then keeps the
strategy, the numbers and the PDFs where you can find them again.

> **Beta.** It works and is used daily, but interfaces, file names and stored
> formats can still change between versions. Problems and suggestions:
> [open an issue](https://github.com/nugh75/Ricerca-scientifica/issues).

**English** · [Italiano](#italiano)

![Suggested searches](https://raw.githubusercontent.com/nugh75/Ricerca-scientifica/main/docs/screenshot/2-ricerche-suggerite.png)

## Download and run

Grab the archive for your system from the
[Releases](https://github.com/nugh75/Ricerca-scientifica/releases) page,
extract it and start it:

| System | Archive | How to start |
|---|---|---|
| macOS | `ricerca-*-macos.tar.gz` | drag `Ricerca.app` into Applications; first launch, right-click → *Open* |
| Windows | `ricerca-*-windows.zip` | double-click `start.bat`; `create-shortcut-windows.bat` puts an icon on the Desktop |
| Linux | `ricerca-*-linux.tar.gz` | `./start.sh`; `install-shortcut-linux.sh` adds it to the menu |

**Python is not required.** On first run the launcher downloads `uv` into the
app folder and lets it fetch the interpreter and the libraries: no admin
rights, no system changes, no `PATH` edits. Only an internet connection the
first time.

Ricerca opens in **its own window**, without address bar or tabs: the launcher
looks for a Chromium-family browser (Chrome, Edge, Brave, Vivaldi) and starts
it in app mode. With Safari, *Share → Add to Dock* gives the same result; on
Chrome and Edge, *Install app* does. Closing the window quits the app, and
`ricerca serve --scheda` asks for a plain tab instead.

The server listens on `127.0.0.1` only: it is never reachable from another
machine.

**Upgrading**: download the new archive and start it. The launcher compares the
version with the installed one and rebuilds the environment when needed. The
running version is printed at the foot of every page; Settings shows which copy
is running, and from which folder.

## First launch

A guided setup explains every setting: what it is for, what changes if you fill
it in, what happens if you leave it empty. It covers installing **Ollama**,
which models fit *this* machine — memory and processor are detected, so the
advice runs from the small Gemma 4 builds up to qwen3.8 where there is room —
and the networked alternatives, **DeepSeek** and **OpenAI**, with addresses,
models, costs and where to get a key. Nothing is required: you can skip it and
configure later, and reopen it any time from Settings.

## How it works

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

Sources queried: OpenAlex, Crossref, PubMed, Europe PMC, arXiv, DOAJ, Semantic
Scholar, CORE, and OPAC SBN for Italian books. For Scopus and Web of Science the
app produces the string to paste into their own interface.

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
.venv/bin/pytest -q                       # 343 tests, none touches the network
.venv/bin/pytest -m rete tests/contratto  # checks the real APIs (weekly in CI)
.venv/bin/uvicorn ricerca.app:app --reload --port 8000
```

One Python package: FastAPI renders HTML with Jinja2, htmx updates the
fragments. No Node, no build step, no binaries to sign.

| File | What it holds |
|---|---|
| `ricerca/keywords.py` | pulls the terms out of the databases |
| `ricerca/strategy.py` | boolean blocks and per-engine rendering |
| `ricerca/sources/` | one module per engine, one interface |
| `ricerca/search.py` | parallel execution, per-source error isolation |
| `ricerca/lavori.py` | work that carries on when you change page |
| `ricerca/registro.py` | the activity and error log |
| `ricerca/history.py` | search history and screening decisions |
| `ricerca/pdf.py`, `biblioteca.py` | open-access PDFs and their text |
| `ricerca/cache.py` | SQLite response cache, as an httpx transport |
| `ricerca/unpaywall.py` | missing metadata and open copies, from the DOI |
| `ricerca/llm.py` | blocks, translation, five-part summary |
| `ricerca/zotero.py` | sends the included records to Zotero |
| `ricerca/macchina.py` | what the computer can run, which model to suggest |
| `ricerca/finestra.py`, `watchdog.py` | its own window; quits when closed |
| `ricerca/i18n.py` | Italian and English strings |
| `docs/specs/` | the design document (Italian) |

Building the archives: `./scripts/crea-release.sh` (they end up in `dist/`); in
CI, `.github/workflows/release.yml` on every `v*` tag. The archives carry the
source and the launcher only — around 200 KB; the screenshots stay here, where
they are read.

---

# Italiano

> **Beta.** Funziona e si usa tutti i giorni, ma interfaccia, nomi dei file e
> formati salvati possono ancora cambiare da una versione all'altra. Problemi e
> proposte: [apri una segnalazione](https://github.com/nugh75/Ricerca-scientifica/issues).

Assistente di ricerca bibliografica. Trasforma un argomento in parole chiave,
stringhe di ricerca pronte per ogni banca dati e un elenco di articoli da
selezionare — e poi tiene strategia, numeri e PDF dove si ritrovano.

## Scarica e avvia

Dalla pagina [Releases](https://github.com/nugh75/Ricerca-scientifica/releases)
scarica l'archivio del tuo sistema, estrailo e avvia:

| Sistema | Archivio | Avvio |
|---|---|---|
| macOS | `ricerca-*-macos.tar.gz` | trascina `Ricerca.app` in Applicazioni; la prima volta clic destro → *Apri* |
| Windows | `ricerca-*-windows.zip` | doppio clic su `start.bat`; `create-shortcut-windows.bat` mette l'icona sul Desktop |
| Linux | `ricerca-*-linux.tar.gz` | `./start.sh`; `install-shortcut-linux.sh` la mette nel menu |

**Non serve installare Python.** Al primo avvio il lanciatore scarica `uv`
nella cartella dell'app e con esso l'interprete e le librerie: nessun permesso
di amministratore, nessuna modifica al sistema, nessun `PATH` da sistemare.
Serve solo una connessione a internet la prima volta.

Ricerca si apre in una **finestra propria**, senza barra degli indirizzi né
schede: il lanciatore cerca un browser della famiglia Chromium e lo avvia in
modo applicazione. Con Safari lo stesso risultato si ottiene da *Condividi →
Aggiungi al Dock*; su Chrome ed Edge da *Installa applicazione*. Chiudendo la
finestra l'app si chiude, e `ricerca serve --scheda` chiede apposta una scheda.

Il server ascolta solo su `127.0.0.1`: non è raggiungibile da altre macchine.

**Aggiornare**: scarica il nuovo archivio e avvialo. Il lanciatore confronta la
versione con quella installata e rifà l'ambiente quando serve. La versione in
esecuzione è scritta in fondo a ogni pagina; Impostazioni dice quale copia sta
girando, e da quale cartella.

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

Motori interrogati: OpenAlex, Crossref, PubMed, Europe PMC, arXiv, DOAJ,
Semantic Scholar, CORE e OPAC SBN per i libri italiani. Per Scopus e Web of
Science l'app produce la stringa da incollare nella loro interfaccia.

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
.venv/bin/pytest -q                       # 343 test, nessuno tocca la rete
.venv/bin/pytest -m rete tests/contratto  # controlla le API vere (CI settimanale)
.venv/bin/uvicorn ricerca.app:app --reload --port 8000
```

Un solo pacchetto Python: FastAPI rende HTML con Jinja2, htmx aggiorna i
frammenti. Niente Node, niente build, niente binari da firmare. La mappa dei
file è nella tabella della sezione inglese; il documento di progetto sta in
`docs/specs/`.
