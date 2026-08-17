# LitReview backend

Servizio FastAPI locale: ricerca multi-fonte (OpenAlex, Semantic Scholar,
Crossref, DOAJ), download/upload PDF, analisi DeepSeek, libreria SQLite,
export `.bib`.

## Setup

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Test

```bash
.venv/bin/pytest -v
```

## Avvio locale

```bash
.venv/bin/uvicorn litreview.main:app --host 127.0.0.1 --port 8756 --reload
```

Il servizio ascolta solo su `127.0.0.1`: non è mai esposto oltre la macchina
locale. Le chiavi API si configurano via `PUT /settings/keys/{name}` e sono
salvate nel keyring di sistema, mai in chiaro su disco.

## Installazione one-click (release GitHub)

1. Vai su <https://github.com/nugh75/Ricerca-scientifica/releases> e scarica
   lo script del tuo sistema dalla release più recente:
   - Windows: `litreview.bat`
   - macOS: `litreview.command` — binario solo per Apple Silicon (arm64); i
     Mac Intel possono usare la versione Linux in WSL o in una VM
   - Linux: `litreview-unix.sh`
2. Avvio:
   - Windows: doppio click su `litreview.bat`.
   - Linux: `chmod +x litreview-unix.sh` la prima volta, poi
     `./litreview-unix.sh`.
   - macOS: gli asset GitHub non hanno l'exec bit e Gatekeeper mette in
     quarantena i download, quindi Finder può rifiutare il doppio click.
     Da Terminale: `bash ~/Downloads/litreview.command` (una sola volta,
     poi ri-eseguibile con lo stesso comando). Firmare/notarizzare con un
     Developer ID Apple rimuoverebbe questo passaggio: hardening previsto
     per il futuro.
3. Lo script scarica l'ultima versione del backend in `~/.litreview/bin/`,
   avvia il server e apre il browser su `http://127.0.0.1:8756/docs`.
   Ri-eseguirlo aggiorna automaticamente all'ultima release.

Note:
- Non serve installare Python: il binario è autonomo.
- Il servizio gira solo su `127.0.0.1` con chiavi solo nel keyring di
  sistema: nessuna esposizione di rete, sandbox di fatto locale.
- Primo avvio su Windows (SmartScreen): se compare un avviso, scegliere
  "Esegui comunque".
- Se la porta 8756 è occupata, il server si ferma con un messaggio chiaro.

## Note per l'integrazione futura (shell desktop Tauri)

Questo backend è pensato per essere lanciato come sidecar da un'app Tauri
(vedi `docs/superpowers/specs/2026-08-17-literature-review-app-design.md`).
Sarà compilato con PyInstaller in un binario standalone e incluso nel bundle
Tauri tramite `externalBin`. Questa parte è coperta da un piano separato.
