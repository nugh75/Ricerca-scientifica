#!/usr/bin/env bash
# Costruisce gli archivi da pubblicare. / Builds the downloadable archives.
#
# Nessuna compilazione, nessun binario da firmare: dentro c'è il sorgente e
# il lanciatore, che al primo avvio si procura uv (e con esso Python).
set -euo pipefail
cd "$(dirname "$0")/.."

VERSIONE="$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)"
DIST="dist"
rm -rf "$DIST/lavoro" && mkdir -p "$DIST/lavoro"

BASE="$DIST/lavoro/ricerca"
mkdir -p "$BASE"
cp -r ricerca pyproject.toml README.md "$BASE/"
mkdir -p "$BASE/docs" && cp -r docs/screenshot "$BASE/docs/"
find "$BASE" -name '__pycache__' -type d -prune -exec rm -rf {} +

# Linux e macOS: tar.gz, conserva il bit di esecuzione.
for sistema in linux macos; do
  rm -f "$BASE/avvia.sh" "$BASE/avvia.command" "$BASE/avvia.bat"
  if [ "$sistema" = "macos" ]; then
    cp avvia.command "$BASE/avvia.command"
    cp avvia.sh "$BASE/avvia.sh"
  else
    cp avvia.sh "$BASE/avvia.sh"
  fi
  tar -czf "$DIST/ricerca-$VERSIONE-$sistema.tar.gz" -C "$DIST/lavoro" ricerca
done

# Windows: zip con il solo .bat.
rm -f "$BASE/avvia.sh" "$BASE/avvia.command"
cp avvia.bat "$BASE/avvia.bat"
( cd "$DIST/lavoro" && zip -qr "../ricerca-$VERSIONE-windows.zip" ricerca )

rm -rf "$DIST/lavoro"
ls -lh "$DIST"
