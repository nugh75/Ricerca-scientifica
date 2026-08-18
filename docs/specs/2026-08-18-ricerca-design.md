# Ricerca — assistente di strategia di ricerca bibliografica

Data: 2026-08-18 · Stato: fase 1 implementata

Il documento descrive quello che è stato costruito: dove il codice si è
discostato dal progetto iniziale, la differenza è annotata.

## Problema

Chi imposta una revisione della letteratura perde tempo su due cose:
trovare i termini giusti (sinonimi, varianti, vocabolari controllati) e
tradurre quei termini nella sintassi di ogni banca dati. `Ricerca` fa
entrambe le cose e poi esegue le query.

La versione precedente del progetto (LitReview, app desktop Tauri con
sidecar Python congelato) è stata abbandonata: non si installava. Le
cause erano di distribuzione, non di logica — binari non firmati, bit di
esecuzione, Gatekeeper, keyring assente, processo figlio da avviare. Il
nuovo progetto elimina l'intera catena: un solo pacchetto Python, nessun
build step, nessun binario, nessun servizio di sistema.

## Ambito

Fase 1 (questo documento):

1. da un topic in italiano o inglese → concetti, sinonimi, termini
   controllati (MeSH), termini co-occorrenti;
2. → blocchi booleani modificabili dall'utente;
3. → stringa di query nella sintassi di ogni motore;
4. → esecuzione, deduplica, tabella risultati;
5. → export `.bib` e `.csv`.

Fuori ambito, rimandato a fasi successive: libreria persistente e PDF
(fase 2), analisi LLM del testo degli articoli (fase 3).

## Decisioni

| Decisione | Motivo |
|---|---|
| Web app locale, non desktop né CLI | UI comoda senza toolchain di packaging |
| Python solo: FastAPI + Jinja2 + htmx | nessun Node, nessun bundler, nessun `node_modules` |
| HTTP diretto verso le API; CLI `*-pp-cli` opzionali | funziona ovunque; le CLI restano una scorciatoia se presenti |
| Config in `~/.ricerca/config.toml` (chmod 600) | il keyring era una delle cause dei problemi di permessi |
| Email di cortesia e chiavi API solo dall'interfaccia | l'app va distribuita: nessun segreto nel codice, nessun file da scrivere a mano |
| Interfaccia bilingue italiano/inglese | il pubblico dell'app è misto; le stringhe stanno in `ricerca/i18n.py` |
| Avvio con `avvia.sh` / `avvia.bat` | chi scarica l'app ha solo Python: i lanciatori creano l'ambiente al primo uso |
| LLM opzionale, client OpenAI-compatible | copre Ollama, llama-swap, DeepSeek, OpenAI con una sola implementazione |
| Nessun dato fuori da `~/.ricerca/` | nessun `sudo`, nessun `chmod`, nessuna cartella di sistema |

## Architettura

```
ricerca/
  cli.py         avvio: porta libera da 8000, bind 127.0.0.1, apre il browser
  app.py         rotte FastAPI che rendono HTML (htmx aggiorna i frammenti)
  config.py      lettura/scrittura ~/.ricerca/config.toml
  keywords.py    topic -> concetti OpenAlex, MeSH PubMed, co-occorrenze
  strategy.py    concetti -> blocchi booleani -> stringa per motore
  llm.py         client OpenAI-compatible (facoltativo)
  sources/       un modulo per motore, interfaccia unica
  dedup.py       fusione per DOI, poi per titolo normalizzato
  export.py      BibTeX e CSV
  templates/     Jinja2
  static/        htmx.min.js + style.css (nessuna risorsa da CDN)
```

### Interfaccia delle fonti

```python
class Source:
    id: str            # "openalex"
    label: str         # "OpenAlex"
    executable: bool   # False = produce solo la stringa da incollare
    key_field: str     # campo di Config che contiene la chiave, se serve
    def render_query(self, strategy: Strategy) -> str: ...
    def unavailable_reason(self, config: Config, lang: str) -> str | None: ...
    async def search(self, client, query: str, limit: int, config: Config) -> list[Work]: ...
```

`Work`: `title, authors, year, doi, venue, url, abstract, oa_url, sources`
(`sources` è una lista: dopo la deduplica un record porta il nome di tutte le
fonti in cui è comparso).

Motori eseguibili: OpenAlex, PubMed, Europe PMC, arXiv, DOAJ, Semantic
Scholar (chiave consigliata, senza chiave risponde spesso `429`), CORE
(chiave obbligatoria), OPAC SBN (libri italiani, via CLI se presente).
Solo stringa copiabile, senza esecuzione: Scopus, Web of Science.

### Estrazione dei termini

Verificata sul campo il 2026-08-18:

- `GET api.openalex.org/text/concepts?title=<topic>` → concetti con score;
- `GET api.openalex.org/text/topics?title=<topic>` → topic primario e campo;
- `GET eutils.ncbi.nlm.nih.gov/.../esearch.fcgi?db=pubmed&term=<topic>` →
  `translationset` contiene la traduzione in termini MeSH;
- primi 50 titoli OpenAlex sul topic → conteggio di unigrammi e bigrammi,
  al netto di una lista di stopword italiane e inglesi.

`/text/keywords` di OpenAlex risponde `500`: non usato.

L'LLM, se configurato, riceve i termini raccolti e li riorganizza in
blocchi concettuali con sinonimi italiani e inglesi, restituendo JSON. Se
manca o fallisce, i blocchi si costruiscono per euristica sui punteggi.
L'app resta pienamente utilizzabile senza LLM.

Dettagli emersi durante l'implementazione:

- l'apostrofo separa le parole (`dell'intelligenza` → `intelligenza`) e i
  frammenti di elisione sono stopword: senza questo i termini più frequenti
  erano `dell` e `dell intelligenza`;
- `ai` non è una stopword italiana ma l'acronimo di *artificial
  intelligence*; come termine singolo è troppo generico, quindi conta solo
  dentro i bigrammi;
- un argomento più lungo di tre parole significative non viene cercato come
  frase esatta ma scomposto nelle sue parole: la frase intera non trova nulla;
- le chiamate di estrazione ritentano fino a tre volte con pausa crescente su
  `429` e `5xx`.

Senza email di cortesia OpenAlex mette il chiamante nel pool condiviso e
risponde spesso `429`: la pagina iniziale chiede l'email al primo avvio e la
nota di errore rimanda lì.

### Sintassi per motore

Da uno `Strategy` (lista di blocchi, ogni blocco lista di termini in OR,
blocchi in AND) ogni fonte produce la propria stringa:

| Motore | Forma |
|---|---|
| OpenAlex | `("a" OR "b") AND ("c")` |
| PubMed | `("a"[tiab] OR "b"[tiab]) AND ("X"[MeSH Terms] OR ...)`, il gruppo MeSH solo se il campo è compilato |
| Europe PMC | `(TITLE_ABS:"a" OR TITLE_ABS:"b") AND (...)` |
| arXiv | `(all:"a" OR all:"b") AND (...)` |
| DOAJ | `("a" OR "b") AND (...)` sul campo predefinito, non solo il titolo |
| CORE | `("a" OR "b") AND (...)` |
| Semantic Scholar | termini principali separati da spazio (niente booleani) |
| OPAC SBN | termini principali separati da spazio |
| Scopus | `TITLE-ABS-KEY(("a" OR "b") AND (...))` |
| Web of Science | `TS=(("a" OR "b") AND (...))` |

### Errori

Ogni fonte ha timeout di 15 secondi e un solo tentativo di ripetizione.
Le fonti girano in parallelo e sono isolate: il fallimento di una produce
una riga di errore accanto al suo nome, mai una pagina vuota. Una fonte
che richiede una chiave assente viene mostrata disattivata, con il motivo.

## Test

`pytest` con `respx` per simulare le risposte HTTP. Per ogni fonte un
test di parsing su una risposta reale salvata come fixture e un test di
resa della query. Test end-to-end: topic → strategia → query → risultati
simulati → `.bib`. Nessun test tocca la rete.

## Avvio

```bash
./avvia.sh                # Linux e macOS; avvia.bat su Windows
uv run ricerca serve      # oppure: pip install -e . && ricerca serve
```

Nessuna chiave è necessaria per partire: le fonti che ne richiedono una
restano disattivate finché non viene inserita dalla pagina Impostazioni.
Le chiavi non vengono mai rese nell'HTML: un campo vuoto conserva la chiave
salvata, la spunta *rimuovi* la cancella.

## Stato

Fase 1 completa: 70 test, nessuno tocca la rete. Schermate in
`docs/screenshot/`.

Fasi successive, ancora da progettare: libreria persistente con PDF (fase 2)
e analisi LLM del testo degli articoli (fase 3). Ognuna avrà il proprio
documento di progetto.
