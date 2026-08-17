# One-Click Release: design spec

**Data:** 2026-08-17
**Stato:** approvato (design in chat approvato dall'utente; esecuzione in autonomia)

## Obiettivo

Distribuire il backend LitReview come release GitHub one-click: l'utente
scarica un unico file (script launcher del proprio OS) dalla pagina Release,
fa doppio click, e ottiene server attivo + browser aperto sulla UI API
(`http://127.0.0.1:8756/docs`). Nessun prerequisito sul PC target
(no Python, no installazioni) grazie a binari PyInstaller onefile.

## Non-obiettivi

- GUI desktop (app Tauri): piano separato futuro; questo spec copre solo
  backend + browser.
- Interfaccia web dedicata: si usa Swagger UI integrato di FastAPI.
- Firma codice / notarizzazione binari (Windows SmartScreen, macOS Gatekeeper
  potranno avvisare: accettato, fuori scope).
- Auto-update in background: l'update avviene a ogni esecuzione dello script
  (scarica sempre `latest`).

## Architettura

Quattro componenti, ciascuno testabile in isolamento:

### 1. Entry point CLI (`backend/src/litreview/__main__.py`)

- `python -m litreview` avvia uvicorn su `127.0.0.1:8756`.
- Apertura browser: thread timer dopo ~1.5s su `http://127.0.0.1:8756/docs`
  con `webbrowser.open`; disattivata se env `LITREVIEW_NO_BROWSER=1`.
- Porta occupata: cattura `OSError`/bind error, messaggio chiaro con istruzione
  su quale processo chiude la porta, exit code 1.
- Log uvicorn su stdout; nel binario frozen con `console=False`, redirect a
  `~/.litreview/server.log`.

### 2. PyInstaller (`backend/packaging/litreview.spec`)

- Onefile, nome artefatto per OS: `litreview-backend-<os>.exe` /
  `litreview-backend-<os>` (os = `windows`, `macos`, `linux`).
- `console=False` su Windows/macOS (nessuna finestra terminale), `console=True`
  su Linux (lo script parte da terminale, log visibili).
- Log: con `console=False` uvicorn scrive su `~/.litreview/server.log`.
- `collect_submodules("keyring.backends")`: keyring usa entry points per i
  backend nativi (WinCred, macOS Keychain, SecretService); senza collect il
  binario parte ma `get_key` fallisce con NoKeyringError ovunque.
- Dati utente invariati: `APP_DIR = ~/.litreview` (config.py invariato).

### 3. CI release (`.github/workflows/release.yml`)

- Trigger: push di tag `v*` (es. `v0.1.0`).
- Job per OS (windows-latest, macos-latest, ubuntu-latest), paralleli:
  1. checkout, setup-python 3.12, `pip install -e ".[dev]" pyinstaller`
  2. build con spec
  3. smoke test sul binario vero: avvio con `LITREVIEW_NO_BROWSER=1`,
     attesa health (`curl --fail http://127.0.0.1:8756/docs`, retry fino a
     30s), kill, fail job se timeout
  4. upload artifact
- Job `release` (dopo i 3): `softprops/action-gh-release` con i 3 binari +
  i 3 launcher script.

### 4. Launcher scripts (`backend/packaging/launchers/`)

- `litreview.bat` (Windows), `litreview.command` (macOS, doppio click da
  Finder), `litreview.sh` (Linux).
- Comportamento identico: scarica binario del proprio OS da
  `https://github.com/nugh75/Ricerca-scientifica/releases/latest/download/<asset>`
  in `~/.litreview/bin/` (curl), esegue. Ri-esecuzione = update automatico.
- Errori download: messaggio leggibile + exit non-zero (niente crash muti).
- Windows: usare `curl.exe` (presente da Windows 10 1803); fallback a
  PowerShell `Invoke-WebRequest` se `curl.exe` manca.

## Flusso utente finale

1. Apri pagina Release su GitHub → scarica lo script del proprio OS.
2. Doppio click (o `./litreview.sh` su Linux).
3. Script scarica il binario latest → binario parte → browser si apre su
   `/docs` → tutto pronto.

## Error handling riepilogato

| Evento | Comportamento |
|---|---|
| Porta 8756 occupata | messaggio chiaro, exit 1 |
| Download script fallito | messaggio, exit 1 |
| Keyring assente (Linux headless) | 503 sulle rotte settings (già implementato); ricerca funziona anonimo |
| `LITREVIEW_NO_BROWSER=1` | nessuna apertura browser (CI, headless) |

## Verifica

- Suite pytest invariata (104 test) — nessuna modifica a `main.py`/router.
- Smoke test CI su binario vero per ogni OS (health + timeout).
- Verifica locale qui (WSL): build PyInstaller Linux + `LITREVIEW_NO_BROWSER=1`
  + curl health + avvio con browser su questo desktop.

## Versioning

- Prima release: `v0.1.0`.
- Asset naming stabile (non include numero versione) così lo script launcher
  punta sempre a `releases/latest/download/…` senza modifiche future.

## Rischi noti

- PyInstaller + keyring: mitigato con collect_submodules; smoke test CI lo
  verifica realmente.
- macOS Gatekeeper / Windows SmartScreen: primo avvio può richiedere "apri
  comunque" — fuori scope, documentato nel README.
- Uvicorn hidden imports: PyInstaller hooks uvicorn standard; se la build
  fallisce, aggiungere `collect_submodules("uvicorn")` — il piano prevede
  questo fallback.
