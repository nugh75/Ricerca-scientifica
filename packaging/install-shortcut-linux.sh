#!/usr/bin/env bash
# Mette Ricerca fra le applicazioni del menu (Linux).
# Adds Ricerca to the applications menu (Linux).
set -euo pipefail
CARTELLA="$(cd "$(dirname "$0")" && pwd)"
DESTINAZIONE="$HOME/.local/share/applications"
mkdir -p "$DESTINAZIONE"

cat > "$DESTINAZIONE/ricerca.desktop" <<FINE
[Desktop Entry]
Type=Application
Name=Ricerca
Comment=Assistente di strategia di ricerca bibliografica
Exec=$CARTELLA/start.sh
Icon=$CARTELLA/ricerca/static/icona.png
Terminal=false
Categories=Education;Science;
FINE

chmod +x "$DESTINAZIONE/ricerca.desktop"
echo "Fatto: cerca «Ricerca» fra le applicazioni."
echo "Done: look for “Ricerca” in your applications menu."
