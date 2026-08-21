#!/bin/bash
# Installa o aggiorna il bundle in /Applications/Ricerca.app quando possibile,
# altrimenti in ~/Applications/Ricerca.app, senza privilegi di amministratore.
# Installs or updates in /Applications/Ricerca.app when possible, otherwise in
# ~/Applications/Ricerca.app, without administrator privileges.
set -euo pipefail

SORGENTE="$(cd "$(dirname "$0")" && pwd)/Ricerca.app"
if [ -w "/Applications" ]; then
  BASE="/Applications"
else
  BASE="$HOME/Applications"
fi
DESTINAZIONE="$BASE/Ricerca.app"
TEMPORANEA="$BASE/.Ricerca-install-$$.app"
PRECEDENTE="$BASE/Ricerca-previous.app"

mkdir -p "$BASE"
trap 'rm -rf "$TEMPORANEA"' EXIT
ditto "$SORGENTE" "$TEMPORANEA"

# Resta una sola copia precedente per un eventuale ripristino.
rm -rf "$PRECEDENTE"
if [ -d "$DESTINAZIONE" ]; then
  mv "$DESTINAZIONE" "$PRECEDENTE"
fi
if ! mv "$TEMPORANEA" "$DESTINAZIONE"; then
  [ ! -d "$DESTINAZIONE" ] && [ -d "$PRECEDENTE" ] && mv "$PRECEDENTE" "$DESTINAZIONE"
  exit 1
fi
trap - EXIT

echo "Ricerca aggiornata in $DESTINAZIONE"
echo "Ricerca updated in $DESTINAZIONE"
open "$DESTINAZIONE"
