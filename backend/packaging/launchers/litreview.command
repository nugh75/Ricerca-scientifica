#!/bin/bash
set -euo pipefail

BASE_URL="${LITREVIEW_ASSET_URL:-https://github.com/nugh75/Ricerca-scientifica/releases/latest/download}"
TMP_DIR="$(mktemp -d)"

if ! command -v curl >/dev/null 2>&1; then
  echo "Errore: curl non trovato. Installalo e riprova." >&2
  exit 1
fi

if ! curl -fsSL --retry 3 -o "$TMP_DIR/litreview-unix.sh" "$BASE_URL/litreview-unix.sh"; then
  echo "Errore: download fallito da $BASE_URL/litreview-unix.sh" >&2
  exit 1
fi

exec bash "$TMP_DIR/litreview-unix.sh"
