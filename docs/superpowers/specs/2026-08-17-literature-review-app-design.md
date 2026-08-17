# App desktop per ricerca bibliografica e analisi PDF con AI — Design Spec

Data: 2026-08-17
Stato: approvato per implementazione (in attesa di review finale utente)

## Obiettivo

Applicazione desktop installabile su Windows, macOS e Linux, con interfaccia
grafica, per:

- cercare articoli scientifici su più fonti (OpenAlex, Semantic Scholar,
  Crossref, DOAJ)
- scaricare i PDF open access disponibili
- analizzare il contenuto dei PDF con l'API DeepSeek (riassunto, estrazione
  metadati, chat Q&A, verifica bibliografica)
- gestire una libreria locale ed esportarla in formato `.bib`, compatibile
  con gli skill esistenti `article-revision` e `bibliography-verify`

Requisito guida: installazione semplice per utenti non tecnici (ricercatori),
un click, nessuna dipendenza esterna da installare a mano (niente Python o
Node richiesti sulla macchina dell'utente finale).

## Scope

**In scope (v1):**
- ricerca multi-fonte con fan-out parallelo e deduplica risultati
- download PDF open access, upload manuale se non disponibile
- analisi DeepSeek: riassunto, estrazione metadati, chat Q&A, verifica bib
- libreria locale SQLite + export `.bib`
- wizard di configurazione al primo avvio (chiavi API), skippabile
- schermata Impostazioni sempre raggiungibile per gestire le chiavi
- installer nativi per Windows/macOS/Linux via CI

**Fuori scope (v1):**
- auto-update dell'applicazione (release manuale via GitHub Releases)
- firma codice/notarizzazione macOS (Gatekeeper mostrerà warning, documentato)
- sincronizzazione cloud/multi-dispositivo della libreria
- integrazione OPAC SBN e Google Scholar (esclusi per instabilità/captcha;
  valutabili in versione futura)
- test E2E automatizzati del frontend (solo test manuale dei flussi critici)
- collaborazione multi-utente / condivisione libreria

## Architettura

```
┌───────────────────────────────┐
│ Tauri shell (Rust)             │  → finestra nativa, installer, IPC,
│                                 │     lifecycle del sidecar
│  ┌───────────────────────────┐ │
│  │ Frontend (HTML/JS/Svelte)   │ │  → UI: Onboarding, Impostazioni,
│  └────────────┬────────────────┘ │     Ricerca, Libreria, Analisi/Chat
│                │ HTTP localhost   │
│  ┌─────────────▼───────────────┐ │
│  │ Python sidecar (FastAPI)      │ │  → binario PyInstaller one-file,
│  │  - client API sorgenti         │ │     spawnato da Tauri all'avvio
│  │  - download/estrazione PDF     │ │
│  │  - client DeepSeek              │ │
│  │  - SQLite libreria              │ │
│  │  - keyring (chiavi API)         │ │
│  └─────────────────────────────────┘ │
└───────────────────────────────┘
```

Tauri gestisce il ciclo di vita del sidecar (spawn all'avvio dell'app, kill
alla chiusura). Il frontend comunica esclusivamente con il backend Python via
REST su `localhost`, porta scelta dinamicamente all'avvio. Nessun dato transita
per server propri: le uniche chiamate di rete sono verso OpenAlex, Semantic
Scholar, Crossref, DOAJ e DeepSeek, effettuate direttamente dalla macchina
dell'utente.

## Componenti

### Frontend
- Onboarding wizard (primo avvio)
- Impostazioni (chiavi API, sempre raggiungibile)
- Ricerca (query + selezione fonti + risultati)
- Libreria (articoli salvati, stato PDF/analisi)
- Dettaglio articolo (riassunto, metadati estratti, chat Q&A, verifica bib)
- Export .bib

### Backend Python (sidecar)
- `api_clients/` — un client per fonte (`openalex.py`, `semantic_scholar.py`,
  `crossref.py`, `doaj.py`), ciascuno normalizza la risposta a uno schema
  comune: `title, authors, year, doi, abstract, oa_pdf_url, source`
- `pdf.py` — download PDF (se `oa_pdf_url` disponibile) + estrazione testo
  (`pdfplumber`/`pypdf`); rileva estrazione vuota/troppo corta (PDF scansionato)
- `deepseek.py` — client DeepSeek (API compatibile OpenAI SDK), 4 modalità:
  riassunto, estrazione metadati, chat Q&A, verifica bibliografica (riusa il
  pattern di similarity scoring di `bib_verify_online.py`)
- `db.py` — SQLite locale
- `keys.py` — gestione chiavi via libreria `keyring` (Credential
  Manager/macOS Keychain/Secret Service Linux), mai salvate in plaintext
- `bib_export.py` — genera `.bib` con citekey stile `AutoreANNOTitolo`,
  compatibile con gli skill `article-revision`/`bibliography-verify`
- API HTTP (FastAPI) esposta al frontend

### Comunicazione Frontend-Backend
REST su `http://127.0.0.1:<porta>`, porta libera scelta all'avvio e passata
al frontend via variabile d'ambiente Tauri. Nessuna autenticazione necessaria
(solo processo locale, porta non esposta all'esterno).

## Modello dati (SQLite)

**`articles`**
`id, title, authors, year, doi, source, abstract, oa_pdf_url, pdf_path,
extracted_text_ok (bool), note, bib_key, analysis_json, created_at`

**`chat_sessions`**
`id, article_id, messages_json, created_at, updated_at`

**`settings`**
flag `first_run_done` (bool); le chiavi API NON sono in questa tabella, vivono
nel keyring di sistema.

## Flussi principali

### Onboarding / primo avvio
1. Al primo avvio (`first_run_done` non settato) parte wizard a step:
   - Benvenuto
   - Chiavi: OpenAlex mailto, Semantic Scholar key (opzionale), Crossref UA
     email, DeepSeek API key — ogni campo ha pulsante "Testa connessione"
     (chiamata leggera di validazione alla fonte)
   - Pulsante "Salta, configuro dopo" sempre visibile → entra in app con le
     fonti/DeepSeek non configurati disattivati (badge "non configurato")
   - "Salva e continua" → scrive chiavi via keyring, marca `first_run_done=true`
2. Schermata **Impostazioni**, sempre raggiungibile da menu, stessi campi e
   stesso test di connessione, riutilizzabile in ogni momento (anche per
   rifare il wizard da capo)
3. Ricerca/Analisi disabilitano solo la fonte con chiave mancante, non
   bloccano l'intera app

### Ricerca
1. Utente inserisce query + seleziona fonti attive (solo quelle configurate)
2. Fan-out parallelo alle fonti selezionate
3. Merge e deduplica risultati (per DOI, fallback su similarity title)
4. Tabella risultati con badge per fonte, stato OA disponibile o meno

### Download PDF
1. Utente seleziona articolo(i) → "Scarica PDF" se `oa_pdf_url` presente
2. Salvato in cartella locale libreria + record in SQLite
3. Se non disponibile: stato "PDF non disponibile" + pulsante upload manuale
   (file picker)

### Analisi DeepSeek
1. Utente sceglie modalità (riassunto / estrazione metadati / verifica bib)
   su un articolo con PDF disponibile
2. Backend estrae testo dal PDF; se estrazione vuota/troppo corta (scansione
   senza OCR) blocca la chiamata DeepSeek e avvisa l'utente
3. Modalità "verifica bib": confronta i metadati letti nel PDF stesso
   (titolo/autori/anno estratti dal testo) con il record salvato in libreria,
   per intercettare PDF scaricati per errore o non corrispondenti (diverso
   dal controllo di `bib_verify_online.py`, che confronta il `.bib` con le
   API esterne, non con il contenuto del file scaricato)
4. Testo troppo lungo per il context window del modello: troncato alle prime
   N pagine/caratteri (soglia configurabile, default prime ~30 pagine), con
   avviso in UI che l'analisi è parziale
5. Chiamata DeepSeek con prompt per modalità scelta, risultato salvato in
   `analysis_json`, mostrato nel dettaglio articolo

### Chat Q&A
Pannello separato nel dettaglio articolo: testo PDF come contesto (stessa
troncatura per PDF molto lunghi, vedi sopra), conversazione multi-turno via
DeepSeek, storicizzata in `chat_sessions`.

### Export .bib
Utente seleziona sottoinsieme libreria → "Esporta .bib" → genera file BibTeX
con citekey coerenti, salvabile in path a scelta (tipicamente
`bibliography/reference.bib` di un progetto `article-revision`).

## Gestione chiavi API

- Mai plaintext su disco: libreria `keyring` (Credential Manager Windows,
  Keychain macOS, Secret Service/libsecret Linux)
- Test di connessione per ogni chiave prima del salvataggio (facoltativo,
  l'utente può forzare il salvataggio anche se il test fallisce)
- Chiavi gestite: OpenAlex mailto/UA, Semantic Scholar API key (opzionale,
  funziona anche senza ma con rate limit più basso), Crossref UA email,
  DeepSeek API key

## Error handling

- Fonte down/rate-limit/timeout → badge rosso sulla fonte nei risultati,
  le altre fonti continuano, retry manuale
- Chiave invalida al test → messaggio inline sotto il campo
- PDF OA non trovato → upload manuale disponibile
- PDF senza testo estraibile → avviso, blocco chiamata DeepSeek (evita
  sprecare costo API su contenuto vuoto)
- Errore DeepSeek (quota/rete/timeout) → messaggio chiaro, risultato parziale
  non perso, retry sul singolo articolo
- Crash sidecar Python → Tauri rileva l'uscita del processo, banner "backend
  non risponde", un tentativo di auto-restart, poi invito a riavviare l'app

## Testing

- Backend: pytest — client API (mock risposte HTTP), estrazione PDF,
  merge/dedup risultati, export `.bib` (formato citekey), CRUD SQLite
- Endpoint: FastAPI `TestClient`, fonti esterne mockate
- Frontend: test manuale dei flussi critici (ricerca → selezione → download
  → analisi → chat → export); nessun E2E automatizzato in v1
- CI: GitHub Actions matrix (windows-latest/macos-latest/ubuntu-latest) —
  pytest sul backend + `cargo tauri build` per generare gli installer dei 3 OS
  ad ogni tag di release

## Packaging & distribuzione

- Tauri bundler produce: `.msi`/`.exe` (Windows), `.dmg` (macOS, non firmato
  in v1 → warning Gatekeeper noto e documentato in README), `.deb` +
  `.AppImage` (Linux)
- Sidecar Python compilato con PyInstaller one-file, incluso nel bundle Tauri
  come binario esterno (`tauri.conf.json` → `externalBin`)
- Nessun auto-update in v1: release manuale su GitHub Releases, l'utente
  riscarica l'installer per aggiornare
- Nessuna telemetria/analytics

## Domande aperte / decisioni future

- Valutare in versione futura: integrazione OPAC SBN e Google Scholar,
  firma codice per macOS/Windows, auto-update, OCR per PDF scansionati
