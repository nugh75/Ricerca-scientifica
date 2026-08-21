#!/usr/bin/env bash
# Ricerca — avvio su Linux e macOS. / Start Ricerca on Linux and macOS.
#
# Non serve installare nulla: se manca Python, lo scarica uv dentro questa
# cartella. Niente sudo, niente modifiche al sistema.
# Nothing to install: if Python is missing, uv fetches it into this folder.
set -euo pipefail
cd "$(dirname "$0")"

TOOLS="$PWD/.tools"
SCRIVIBILE=1

# Se la cartella dell'app non è scrivibile (per esempio /Applications o una
# chiavetta protetta), tutto finisce sotto ~/.ricerca: nessun permesso da
# chiedere. / If the app folder is read-only, everything goes to ~/.ricerca.
if [ ! -w "$PWD" ] || [ -f "$PWD/.installed" ]; then
  SCRIVIBILE=0
  TOOLS="$HOME/.ricerca/tools"
  mkdir -p "$TOOLS"
fi

trova_uv() {
  if command -v uv > /dev/null 2>&1; then command -v uv; return; fi
  if [ -x "$TOOLS/uv" ]; then echo "$TOOLS/uv"; return; fi
  echo ""
}

UV="$(trova_uv)"

if [ -z "$UV" ]; then
  echo "Preparazione al primo avvio… / First-run setup…"
  if command -v curl > /dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$TOOLS" UV_NO_MODIFY_PATH=1 sh > /dev/null 2>&1 || true
  elif command -v wget > /dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$TOOLS" UV_NO_MODIFY_PATH=1 sh > /dev/null 2>&1 || true
  fi
  UV="$(trova_uv)"
fi

if [ -n "$UV" ]; then
  if [ "$SCRIVIBILE" = "1" ]; then
    exec "$UV" run --quiet ricerca serve "$@"
  fi
  # Cartella in sola lettura: ambiente separato, installazione non editabile,
  # niente file scritti accanto al sorgente.
  VENV="$HOME/.ricerca/venv"
  VERSIONE="$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)"
  INSTALLATA="$(cat "$VENV/.versione" 2>/dev/null || true)"
  # Senza questo confronto un ambiente creato una volta resterebbe per
  # sempre: chi scarica una versione nuova continuerebbe a eseguire la
  # vecchia senza capire perché.
  if [ ! -x "$VENV/bin/ricerca" ] || [ "$INSTALLATA" != "$VERSIONE" ]; then
    echo "Preparazione dell'ambiente in ~/.ricerca … / Setting up ~/.ricerca …"
    "$UV" venv --quiet --clear --python 3.12 "$VENV"
    "$UV" pip install --quiet --python "$VENV/bin/python" .
    echo "$VERSIONE" > "$VENV/.versione"
  fi
  exec "$VENV/bin/ricerca" serve "$@"
fi

# Ripiego: Python di sistema. / Fallback: system Python.
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" > /dev/null 2>&1; then
  echo "Non sono riuscito a scaricare uv e non trovo Python 3.11+."
  echo "Could not download uv and no Python 3.11+ found."
  echo "Installa Python da https://www.python.org/downloads/ e riprova."
  exit 1
fi
VENV_FALLBACK="$PWD/.venv"
if [ "$SCRIVIBILE" = "0" ]; then
  VENV_FALLBACK="$HOME/.ricerca/venv"
fi
VERSIONE="$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)"
INSTALLATA="$(cat "$VENV_FALLBACK/.versione" 2>/dev/null || true)"
if [ ! -x "$VENV_FALLBACK/bin/ricerca" ] || [ "$INSTALLATA" != "$VERSIONE" ]; then
  "$PYTHON" -m venv --clear "$VENV_FALLBACK"
  "$VENV_FALLBACK/bin/pip" install --quiet --upgrade pip
  if [ "$SCRIVIBILE" = "1" ]; then
    "$VENV_FALLBACK/bin/pip" install --quiet -e .
  else
    "$VENV_FALLBACK/bin/pip" install --quiet .
  fi
  echo "$VERSIONE" > "$VENV_FALLBACK/.versione"
fi
exec "$VENV_FALLBACK/bin/ricerca" serve "$@"
