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

## Note per l'integrazione futura (shell desktop Tauri)

Questo backend è pensato per essere lanciato come sidecar da un'app Tauri
(vedi `docs/superpowers/specs/2026-08-17-literature-review-app-design.md`).
Sarà compilato con PyInstaller in un binario standalone e incluso nel bundle
Tauri tramite `externalBin`. Questa parte è coperta da un piano separato.
