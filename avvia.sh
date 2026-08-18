#!/usr/bin/env bash
# Avvio di Ricerca su Linux e macOS. / Start Ricerca on Linux and macOS.
# Crea un ambiente Python locale la prima volta, poi apre l'app nel browser.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" > /dev/null; then
  echo "Serve Python 3.11 o superiore. / Python 3.11+ is required."
  echo "macOS: brew install python   ·   Linux: sudo apt install python3-venv"
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Preparazione dell'ambiente… / Preparing the environment…"
  "$PYTHON" -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -e .
fi

exec .venv/bin/ricerca serve "$@"
