# Ricerca

Assistente di strategia di ricerca bibliografica. Da un topic ricava parole
chiave, termini controllati e stringhe di ricerca pronte per ogni banca dati,
poi esegue le query e ne esporta i risultati.

![Ricerche suggerite](docs/screenshot/2-ricerche-suggerite.png)

## Che cosa fa

1. **Topic** — lo scrivi in italiano o in inglese.
2. **Ricerche suggerite** — concetti da OpenAlex, termini MeSH da PubMed,
   termini che ricorrono nei titoli dei primi risultati; da questi nascono i
   blocchi booleani, modificabili a mano, e le stringhe per ogni motore.
   Nessuna ricerca parte finché non la avvii tu.
3. **Risultati** — le fonti scelte vengono interrogate in parallelo, i
   duplicati uniti per DOI o titolo, l'elenco esportato in `.bib` o `.csv`.

Motori interrogati: OpenAlex, PubMed, Europe PMC, arXiv, DOAJ, Semantic
Scholar (meglio con chiave), CORE (chiave gratuita), OPAC SBN per i libri
italiani (usa la CLI `opac-sbn-pp-cli`, se installata). Per Scopus e Web of
Science l'app produce la stringa da incollare nella loro interfaccia.

## Avvio

```bash
uv run ricerca serve          # oppure: pip install -e . && ricerca serve
```

Si apre il browser su `http://127.0.0.1:8000` (o la prima porta libera).
Il server ascolta solo su `127.0.0.1`.

Nessuna chiave è obbligatoria. Alla prima ricerca conviene inserire l'**email
di cortesia**: OpenAlex la usa per applicare limiti di richiesta più larghi e
senza di essa risponde spesso `429`.

## LLM (facoltativo)

In Impostazioni puoi indicare un endpoint compatibile con l'API OpenAI —
Ollama (`http://localhost:11434/v1`), llama-swap, DeepSeek, OpenAI — e il
modello. Serve solo a riorganizzare i termini in blocchi concettuali: senza,
l'app costruisce i blocchi dai soli dati e funziona lo stesso.

## Configurazione

Tutto in `~/.ricerca/config.toml`, creato dall'app con permessi `600`:
email di cortesia, endpoint e modello LLM, chiavi Semantic Scholar, CORE e
NCBI. Nessun keyring, nessun percorso di sistema, nessun `sudo`.

## Sviluppo

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest -q                     # 60 test, nessuno tocca la rete
.venv/bin/uvicorn ricerca.app:app --reload --port 8000
```

Il progetto è un solo pacchetto Python: FastAPI rende HTML con Jinja2 e htmx
aggiorna i frammenti di pagina. Niente Node, niente build, niente binari da
firmare.

- `ricerca/keywords.py` — estrazione dei termini dalle banche dati
- `ricerca/strategy.py` — blocchi booleani e resa per motore
- `ricerca/sources/` — un modulo per motore, interfaccia unica
- `ricerca/search.py` — esecuzione parallela, con isolamento degli errori
- `docs/specs/` — il documento di progetto
