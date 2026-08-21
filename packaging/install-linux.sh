#!/usr/bin/env bash
# Installa o aggiorna Ricerca in ~/.local/share/ricerca e la avvia.
# Installs or updates Ricerca in ~/.local/share/ricerca and starts it.
set -euo pipefail

SORGENTE="$(cd "$(dirname "$0")" && pwd)"
BASE_DATI="${XDG_DATA_HOME:-$HOME/.local/share}"
DESTINAZIONE="$BASE_DATI/ricerca"
TEMPORANEA="$BASE_DATI/.ricerca-install-$$"
PRECEDENTE="$BASE_DATI/ricerca-previous"

if [ "$SORGENTE" = "$DESTINAZIONE" ]; then
  exec "$DESTINAZIONE/start.sh"
fi

mkdir -p "$BASE_DATI"
trap 'rm -rf "$TEMPORANEA"' EXIT
mkdir "$TEMPORANEA"
cp -R "$SORGENTE/ricerca" "$TEMPORANEA/"
cp "$SORGENTE/pyproject.toml" "$SORGENTE/README.md" "$SORGENTE/LICENSE" "$TEMPORANEA/"
cp "$SORGENTE/start.sh" "$SORGENTE/install-shortcut-linux.sh" "$TEMPORANEA/"
cp "$SORGENTE/install-or-update.sh" "$TEMPORANEA/"
touch "$TEMPORANEA/.installed"
chmod +x "$TEMPORANEA/start.sh" "$TEMPORANEA/install-shortcut-linux.sh" "$TEMPORANEA/install-or-update.sh"

# Resta una sola copia precedente per poter tornare indietro se necessario.
rm -rf "$PRECEDENTE"
if [ -d "$DESTINAZIONE" ]; then
  mv "$DESTINAZIONE" "$PRECEDENTE"
fi
if ! mv "$TEMPORANEA" "$DESTINAZIONE"; then
  [ ! -d "$DESTINAZIONE" ] && [ -d "$PRECEDENTE" ] && mv "$PRECEDENTE" "$DESTINAZIONE"
  exit 1
fi
trap - EXIT

"$DESTINAZIONE/install-shortcut-linux.sh"
echo "Ricerca aggiornata in $DESTINAZIONE"
echo "Ricerca updated in $DESTINAZIONE"
exec "$DESTINAZIONE/start.sh"
