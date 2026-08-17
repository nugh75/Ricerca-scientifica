# One-Click Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Distribuire il backend LitReview come release GitHub one-click: script launcher per OS scaricato dalla pagina Release, doppio click = server attivo + browser aperto su `/docs`.

**Architecture:** Binari PyInstaller onefile per OS costruiti in GitHub Actions su tag `v*`; script launcher (`.bat`/`.sh`/`.command`) che scaricano l'asset `latest` e lo eseguono; entry point `__main__.py` apre il browser e gestisce porta occupata.

**Tech Stack:** Python 3.12, PyInstaller, GitHub Actions, bash, batch.

**Spec:** docs/superpowers/specs/2026-08-17-one-click-release-design.md

## Global Constraints

- Python >= 3.11 (build in CI con Python 3.12).
- Codice sotto `backend/src/litreview/`; test sotto `backend/tests/`.
- Commit prefix `feat(backend): ...` per codice, `feat(ci): ...` per workflow.
- Nessun placeholder/TODO nei commit.
- Host/porta fissi: `127.0.0.1:8756` (serve sempre solo localhost).
- Asset naming esatto: `litreview-backend-windows.exe`, `litreview-backend-macos`, `litreview-backend-linux` (senza numero versione).
- Env `LITREVIEW_NO_BROWSER=1` disattiva apertura browser; env `LITREVIEW_ASSET_URL` override URL download nei launcher (testabilità).
- Release URL pattern: `https://github.com/nugh75/Ricerca-scientifica/releases/latest/download/<asset>`.
- `console=False` su Windows/macOS (log su `~/.litreview/server.log`), `console=True` su Linux.
- Dati utente invariati: `APP_DIR = ~/.litreview` (config.py invariato).

---

### Task 1: Entry point CLI con browser auto-open

**Files:**
- Create: `backend/src/litreview/__main__.py`
- Modify: `backend/pyproject.toml` (sezione `[project.scripts]`)
- Test: `backend/tests/test_main_entry.py`

**Interfaces:**
- Consumes: `litreview.main.app` (già esistente), `config.APP_DIR`.
- Produces: `main() -> int` (exit code), `_port_in_use(host, port) -> bool`, `_redirect_logs_if_frozen()`, `_open_browser()`; console script `litreview-backend` (usato solo in dev; il binario frozen usa `packaging/run_litreview.py`, Task 2).

- [ ] **Step 1: Scrivere i test che falliscono**

`backend/tests/test_main_entry.py`:

```python
import socket
import sys

import pytest

from litreview import config
from litreview.__main__ import (
    DOCS_URL,
    HOST,
    PORT,
    _open_browser,
    _port_in_use,
    _redirect_logs_if_frozen,
    main,
)


def test_port_in_use_true_when_bound():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.bind((HOST, 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        assert _port_in_use(HOST, port) is True


def test_port_in_use_false_when_free():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.bind((HOST, 0))
        port = srv.getsockname()[1]
    assert _port_in_use(HOST, port) is False


def test_open_browser_opens_docs_url(monkeypatch):
    opened = []
    monkeypatch.setattr("litreview.__main__.webbrowser.open", opened.append)
    _open_browser()
    assert opened == [DOCS_URL]


def test_main_returns_1_when_port_in_use(monkeypatch, capsys):
    monkeypatch.setattr("litreview.__main__._port_in_use", lambda h, p: True)
    monkeypatch.setattr(
        "litreview.__main__.uvicorn.run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("non deve partire"))
    )
    assert main() == 1
    err = capsys.readouterr().err
    assert "8756" in err
    assert "occupat" in err


def test_main_runs_uvicorn_without_browser_when_env_set(monkeypatch):
    monkeypatch.setenv("LITREVIEW_NO_BROWSER", "1")
    monkeypatch.setattr("litreview.__main__._port_in_use", lambda h, p: False)
    timers = []

    class FakeTimer:
        def __init__(self, *args):
            timers.append(args)

        def start(self):
            pass

    monkeypatch.setattr("litreview.__main__.threading.Timer", FakeTimer)
    kwargs = {}
    monkeypatch.setattr(
        "litreview.__main__.uvicorn.run", lambda app, **k: kwargs.update(k)
    )
    assert main() == 0
    assert kwargs == {"host": HOST, "port": PORT, "log_level": "info"}
    assert timers == []


def test_main_schedules_browser_timer_by_default(monkeypatch):
    monkeypatch.delenv("LITREVIEW_NO_BROWSER", raising=False)
    monkeypatch.setattr("litreview.__main__._port_in_use", lambda h, p: False)
    timers = []

    class FakeTimer:
        def __init__(self, *args):
            timers.append(args)

        def start(self):
            pass

    monkeypatch.setattr("litreview.__main__.threading.Timer", FakeTimer)
    monkeypatch.setattr("litreview.__main__.uvicorn.run", lambda *a, **k: None)
    assert main() == 0
    assert len(timers) == 1
    delay, target = timers[0]
    assert delay == 1.5
    assert target is _open_browser


def test_redirect_logs_when_frozen_and_not_tty(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "APP_DIR", tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    class NoTty:
        def isatty(self):
            return False

    monkeypatch.setattr(sys, "stdout", NoTty())
    monkeypatch.setattr(sys, "stderr", NoTty())
    _redirect_logs_if_frozen()
    assert sys.stdout.name == str(tmp_path / "server.log")
    assert sys.stderr is sys.stdout


def test_no_redirect_when_not_frozen(monkeypatch, tmp_path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(config, "APP_DIR", tmp_path)
    before = sys.stdout
    _redirect_logs_if_frozen()
    assert sys.stdout is before


def test_no_redirect_when_frozen_but_tty(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(config, "APP_DIR", tmp_path)

    class Tty:
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdout", Tty())
    before = sys.stdout
    _redirect_logs_if_frozen()
    assert sys.stdout is before
```

- [ ] **Step 2: Eseguire i test per verificare che falliscano**

Run: `cd backend && .venv/bin/pytest tests/test_main_entry.py -v`
Expected: FAIL (module `litreview.__main__` non esiste).

- [ ] **Step 3: Scrivere l'implementazione minima**

`backend/src/litreview/__main__.py`:

```python
import os
import socket
import sys
import threading
import webbrowser

import uvicorn

from . import config

HOST = "127.0.0.1"
PORT = 8756
DOCS_URL = f"http://{HOST}:{PORT}/docs"

BROWSER_DELAY = 1.5


def _open_browser() -> None:
    webbrowser.open(DOCS_URL)


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((host, port)) == 0


def _redirect_logs_if_frozen() -> None:
    if not getattr(sys, "frozen", False):
        return
    if sys.stdout is not None and sys.stdout.isatty():
        return
    config.APP_DIR.mkdir(parents=True, exist_ok=True)
    log_file = open(config.APP_DIR / "server.log", "a", encoding="utf-8")
    sys.stdout = log_file
    sys.stderr = log_file


def main() -> int:
    if _port_in_use(HOST, PORT):
        print(
            f"Impossibile avviare il server: la porta {PORT} e' gia' occupata "
            "da un altro processo. Chiudilo e riprova.",
            file=sys.stderr,
        )
        return 1
    _redirect_logs_if_frozen()
    if os.environ.get("LITREVIEW_NO_BROWSER") != "1":
        threading.Timer(BROWSER_DELAY, _open_browser).start()
    uvicorn.run("litreview.main:app", host=HOST, port=PORT, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`backend/pyproject.toml`, aggiungere sotto `[project]`:

```toml
[project.scripts]
litreview-backend = "litreview.__main__:main"
```

- [ ] **Step 4: Eseguire i test per verificare che passino**

Run: `cd backend && .venv/bin/pytest tests/test_main_entry.py -v`
Expected: 9 PASSED. Poi suite completa: `.venv/bin/pytest -v` → 113 passed (104 + 9), nessuna regressione.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/__main__.py backend/pyproject.toml backend/tests/test_main_entry.py
git commit -m "feat(backend): add CLI entry point with browser auto-open"
```

---

### Task 2: Spec PyInstaller onefile + build locale di verifica

**Files:**
- Create: `backend/packaging/run_litreview.py`
- Create: `backend/packaging/litreview.spec`
- Modify: `.gitignore` (aggiungere `build/`)

**Interfaces:**
- Consumes: `litreview.__main__.main` (Task 1).
- Produces: binari `litreview-backend-<os>` in `backend/dist/` quando eseguito `pyinstaller --distpath dist --workpath build packaging/litreview.spec` da `backend/`. Task 4 (CI) usa lo stesso comando.

- [ ] **Step 1: Scrivere entry per PyInstaller**

`backend/packaging/run_litreview.py`:

```python
from litreview.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Scrivere lo spec**

`backend/packaging/litreview.spec`:

```python
import sys

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("keyring.backends")
# uvicorn.run("litreview.main:app") e' un import per stringa che PyInstaller
# non vede: senza questa collect il bundle parte senza litreview.main/routers
# (exit 3, "Could not import module litreview.main").
hiddenimports += collect_submodules("litreview")

if sys.platform.startswith("win"):
    name = "litreview-backend-windows"
    console = False
elif sys.platform == "darwin":
    name = "litreview-backend-macos"
    console = False
else:
    name = "litreview-backend-linux"
    console = True

a = Analysis(
    ["../packaging/run_litreview.py"],
    pathex=["../src"],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

Nota: i path relativi nello spec sono relativi alla directory dello spec (`backend/packaging/`), quindi `../src` = `backend/src`. Il comando di build va eseguito da `backend/` con `--distpath dist --workpath build`.

- [ ] **Step 3: Aggiungere `build/` al .gitignore**

`.gitignore` (root), aggiungere in coda:

```
build/
```

(`dist/` è già ignorato.)

- [ ] **Step 4: Verifica — build locale Linux**

```bash
cd backend
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller --distpath dist --workpath build packaging/litreview.spec
```

Expected: binario in `backend/dist/litreview-backend-linux`, nessun errore hidden-import. Se la build fallisce con import mancanti di uvicorn, aggiungere `hiddenimports += collect_submodules("uvicorn")` nello spec e riprovare (fallback previsto dallo spec).

- [ ] **Step 5: Verifica — smoke test sul binario**

```bash
cd backend
LITREVIEW_NO_BROWSER=1 ./dist/litreview-backend-linux &
PID=$!
for i in $(seq 1 30); do
  curl -fsS http://127.0.0.1:8756/docs >/dev/null && break
  sleep 1
done
curl -fsS http://127.0.0.1:8756/docs >/dev/null || { echo "SMOKE FAILED"; kill $PID; exit 1; }
kill $PID
echo "SMOKE OK"
```

Expected: `SMOKE OK`. Verificare anche che il binario risponda su una rotta reale, es. `curl -fsS http://127.0.0.1:8756/library` prima del kill.

- [ ] **Step 6: Commit**

```bash
git add backend/packaging/run_litreview.py backend/packaging/litreview.spec .gitignore
git commit -m "feat(backend): add PyInstaller onefile spec for frozen builds"
```

---

### Task 3: Script launcher per OS

**Files:**
- Create: `backend/packaging/launchers/litreview.bat`
- Create: `backend/packaging/launchers/litreview-unix.sh`
- Create: `backend/packaging/launchers/litreview.command`

**Interfaces:**
- Consumes: asset naming (Global Constraints) e URL pattern `releases/latest/download/<asset>`.
- Produces: file distribuiti nella release (Task 4) e documentati nel README (Task 5). Env `LITREVIEW_ASSET_URL` = override base URL per test.

- [ ] **Step 1: Scrivere `litreview-unix.sh`** (unico script per Linux e macOS, detecta l'OS)

`backend/packaging/launchers/litreview-unix.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${LITREVIEW_ASSET_URL:-https://github.com/nugh75/Ricerca-scientifica/releases/latest/download}"

case "$(uname -s)" in
  Darwin) ASSET="litreview-backend-macos" ;;
  Linux) ASSET="litreview-backend-linux" ;;
  *)
    echo "Errore: sistema operativo non supportato." >&2
    exit 1
    ;;
esac

BIN_DIR="$HOME/.litreview/bin"
BIN="$BIN_DIR/$ASSET"

if ! command -v curl >/dev/null 2>&1; then
  echo "Errore: curl non trovato. Installalo e riprova." >&2
  exit 1
fi

mkdir -p "$BIN_DIR"
echo "Scaricamento LitReview backend..."
if ! curl -fsSL --retry 3 -o "$BIN.tmp" "$BASE_URL/$ASSET"; then
  echo "Errore: download fallito da $BASE_URL/$ASSET" >&2
  exit 1
fi
chmod +x "$BIN.tmp"
mv "$BIN.tmp" "$BIN"

exec "$BIN"
```

- [ ] **Step 2: Scrivere `litreview.command`** (doppio click da Finder su macOS)

`backend/packaging/launchers/litreview.command`:

```bash
#!/bin/bash
exec bash "$(cd "$(dirname "$0")" && pwd)/litreview-unix.sh"
```

- [ ] **Step 3: Scrivere `litreview.bat`**

`backend/packaging/launchers/litreview.bat`:

```bat
@echo off
setlocal

set "BASE_URL=%LITREVIEW_ASSET_URL%"
if "%BASE_URL%"=="" set "BASE_URL=https://github.com/nugh75/Ricerca-scientifica/releases/latest/download"
set "ASSET=litreview-backend-windows.exe"
set "BIN_DIR=%USERPROFILE%\.litreview\bin"
set "BIN=%BIN_DIR%\%ASSET%"

if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

where curl.exe >nul 2>&1
if errorlevel 1 goto use_powershell

echo Downloading LitReview backend...
curl.exe -fsSL --retry 3 -o "%BIN%.tmp" "%BASE_URL%/%ASSET%"
if errorlevel 1 (
  echo Errore: download fallito da %BASE_URL%/%ASSET% 1>&2
  exit /b 1
)
move /y "%BIN%.tmp" "%BIN%" >nul
"%BIN%"
exit /b %errorlevel%

:use_powershell
echo Downloading LitReview backend...
powershell -NoProfile -Command "Invoke-WebRequest -Uri '%BASE_URL%/%ASSET%' -OutFile '%BIN%.tmp'"
if errorlevel 1 (
  echo Errore: download fallito da %BASE_URL%/%ASSET% 1>&2
  exit /b 1
)
move /y "%BIN%.tmp" "%BIN%" >nul
"%BIN%"
exit /b %errorlevel%
```

- [ ] **Step 4: Verifica — sintassi e download reale dello script unix**

```bash
cd backend/packaging/launchers
bash -n litreview-unix.sh && echo "syntax OK"
chmod +x litreview-unix.sh litreview.command
```

Poi test end-to-end del download con un server HTTP locale finto che serve un finto binario:

```bash
cd /tmp
mkdir -p fake-release/bin && cd fake-release
printf '#!/bin/sh\necho FAKE-BIN-RUN-OK\n' > litreview-backend-linux
python3 -m http.server 8977 --directory . &
SRV=$!
sleep 1
LITREVIEW_ASSET_URL="http://127.0.0.1:8977" HOME=/tmp/fake-release/home \
  bash /home/nugh75/Ricerca-scientifica/backend/packaging/launchers/litreview-unix.sh
kill $SRV
```

Expected output: `FAKE-BIN-RUN-OK` (lo script ha scaricato ed eseguito il finto binario). `.bat` non eseguibile qui: verifica = solo review del contenuto (coerenza con lo .sh: stessi URL/asset/percorsi).

- [ ] **Step 5: Commit**

```bash
git add backend/packaging/launchers/
git commit -m "feat(backend): add one-click launcher scripts for Windows, macOS, Linux"
```

---

### Task 4: Workflow GitHub Actions di release

**Files:**
- Create: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: spec PyInstaller (Task 2), launcher scripts (Task 3), asset naming (Global Constraints).
- Produces: GitHub Release con 6 asset (3 binari + 3 script) a ogni tag `v*`.

- [ ] **Step 1: Scrivere il workflow**

`.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags:
      - "v*"

permissions:
  contents: write

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install
        run: pip install -e ".[dev]" pyinstaller
        working-directory: backend
      - name: Build
        run: pyinstaller --distpath dist --workpath build packaging/litreview.spec
        working-directory: backend
      - name: Smoke test
        shell: powershell
        working-directory: backend
        run: |
          $env:LITREVIEW_NO_BROWSER = "1"
          $p = Start-Process -FilePath "dist\litreview-backend-windows.exe" -PassThru
          $ok = $false
          for ($i = 0; $i -lt 30; $i++) {
            try {
              $r = Invoke-WebRequest -Uri "http://127.0.0.1:8756/docs" -UseBasicParsing -TimeoutSec 2
              if ($r.StatusCode -eq 200) { $ok = $true; break }
            } catch { Start-Sleep 1 }
          }
          Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
          if (-not $ok) { throw "smoke test fallito: /docs non risponde" }
          Write-Output "SMOKE OK"
      - uses: actions/upload-artifact@v4
        with:
          name: windows-binary
          path: backend/dist/litreview-backend-windows.exe

  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install
        run: pip install -e ".[dev]" pyinstaller
        working-directory: backend
      - name: Build
        run: pyinstaller --distpath dist --workpath build packaging/litreview.spec
        working-directory: backend
      - name: Smoke test
        working-directory: backend
        run: |
          LITREVIEW_NO_BROWSER=1 ./dist/litreview-backend-macos &
          PID=$!
          ok=""
          for i in $(seq 1 30); do
            if curl -fsS http://127.0.0.1:8756/docs >/dev/null; then ok=1; break; fi
            sleep 1
          done
          kill $PID 2>/dev/null || true
          [ -n "$ok" ] || { echo "smoke test fallito: /docs non risponde"; exit 1; }
          echo "SMOKE OK"
      - uses: actions/upload-artifact@v4
        with:
          name: macos-binary
          path: backend/dist/litreview-backend-macos

  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install
        run: pip install -e ".[dev]" pyinstaller
        working-directory: backend
      - name: Build
        run: pyinstaller --distpath dist --workpath build packaging/litreview.spec
        working-directory: backend
      - name: Smoke test
        working-directory: backend
        run: |
          LITREVIEW_NO_BROWSER=1 ./dist/litreview-backend-linux &
          PID=$!
          ok=""
          for i in $(seq 1 30); do
            if curl -fsS http://127.0.0.1:8756/docs >/dev/null; then ok=1; break; fi
            sleep 1
          done
          kill $PID 2>/dev/null || true
          [ -n "$ok" ] || { echo "smoke test fallito: /docs non risponde"; exit 1; }
          echo "SMOKE OK"
      - uses: actions/upload-artifact@v4
        with:
          name: linux-binary
          path: backend/dist/litreview-backend-linux

  release:
    needs: [build-windows, build-macos, build-linux]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          pattern: "*-binary"
          path: artifacts
          merge-multiple: true
      - uses: softprops/action-gh-release@v2
        with:
          files: |
            artifacts/litreview-backend-windows.exe
            artifacts/litreview-backend-macos
            artifacts/litreview-backend-linux
            backend/packaging/launchers/litreview.bat
            backend/packaging/launchers/litreview-unix.sh
            backend/packaging/launchers/litreview.command
```

Nota: i job smoke richiedono che il server parta in <30s. Il binario onefile estrae in temp al primo avvio (~2-5s) — margine abbondante.

- [ ] **Step 2: Verifica — parse YAML**

```bash
cd /home/nugh75/Ricerca-scientifica
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml')); print('YAML OK')"
```

Expected: `YAML OK`.

- [ ] **Step 3: Verifica — coerenza nomi asset**

```bash
grep -n "litreview-backend-" .github/workflows/release.yml | grep -o "litreview-backend-[a-z]*" | sort -u
```

Expected: esattamente `litreview-backend-linux`, `litreview-backend-macos`, `litreview-backend-windows` (i tre nomi degli asset, coerenti con spec e launchers).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "feat(ci): build onefile binaries per OS and create GitHub release on tags"
```

---

### Task 5: README, verifica E2E locale, istruzioni tag

**Files:**
- Modify: `backend/README.md` (sezione "Installazione one-click")

**Interfaces:**
- Consumes: tutto (Task 1-4). Nessuna nuova interfaccia.

- [ ] **Step 1: Aggiungere sezione al README**

In `backend/README.md`, dopo "## Avvio locale" (prima della sezione Tauri):

```markdown
## Installazione one-click (release GitHub)

1. Vai su <https://github.com/nugh75/Ricerca-scientifica/releases> e scarica
   lo script del tuo sistema dalla release più recente:
   - Windows: `litreview.bat`
   - macOS: `litreview.command`
   - Linux: `litreview-unix.sh`
2. Doppio click sullo script (su Linux: `chmod +x litreview-unix.sh` la prima
   volta, poi `./litreview-unix.sh`).
3. Lo script scarica l'ultima versione del backend in `~/.litreview/bin/`,
   avvia il server e apre il browser su `http://127.0.0.1:8756/docs`.
   Ri-eseguirlo aggiorna automaticamente all'ultima release.

Note:
- Non serve installare Python: il binario è autonomo.
- Primo avvio su macOS (Gatekeeper) / Windows (SmartScreen): se compare un
  avviso, scegliere "Apri comunque".
- Se la porta 8756 è occupata, il server si ferma con un messaggio chiaro.
```

- [ ] **Step 2: Verifica E2E locale completa (WSL)**

```bash
cd backend
.venv/bin/pyinstaller --distpath dist --workpath build packaging/litreview.spec  # se non già fatto (Task 2)
LITREVIEW_NO_BROWSER=1 ./dist/litreview-backend-linux &
PID=$!
for i in $(seq 1 30); do curl -fsS http://127.0.0.1:8756/docs >/dev/null && break; sleep 1; done
curl -fsS http://127.0.0.1:8756/library >/dev/null && echo "LIBRARY OK"
curl -fsS http://127.0.0.1:8756/docs >/dev/null && echo "DOCS OK"
kill $PID
```

Expected: `LIBRARY OK` e `DOCS OK`. Poi ri-eseguire il test launcher del Task 3 Step 4 (ancora verde).

- [ ] **Step 3: Commit**

```bash
git add backend/README.md
git commit -m "docs(backend): document one-click release installation"
```

- [ ] **Step 4: Pubblicare la release v0.1.0**

```bash
git tag -a v0.1.0 -m "LitReview backend 0.1.0 — first one-click release"
git push origin main --tags
```

Expected: workflow `Release` verde su GitHub Actions (3 build + smoke + release job) e release `v0.1.0` con 6 asset. Verificare su `https://github.com/nugh75/Ricerca-scientifica/releases` e scaricare `litreview-unix.sh` per provare il flusso utente reale (download da `releases/latest/download`).
