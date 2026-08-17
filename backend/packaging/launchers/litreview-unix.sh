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
