#!/usr/bin/env bash
# Costruisce gli archivi da pubblicare. / Builds the downloadable archives.
#
# Nessuna compilazione, nessun binario da firmare: dentro c'è il sorgente e
# un lanciatore che al primo avvio si procura uv (e con esso Python).
set -euo pipefail
cd "$(dirname "$0")/.."

VERSIONE="$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)"
DIST="dist"
LAVORO="$DIST/lavoro"
rm -rf "$LAVORO" && mkdir -p "$LAVORO"
# `zip` aggiunge a un archivio esistente invece di rifarlo: senza questa
# pulizia un archivio vecchio si porterebbe dentro i file di ieri.
rm -f "$DIST/ricerca-$VERSIONE"-*.tar.gz "$DIST/ricerca-$VERSIONE"-*.zip

sorgente_in() {
  # Copia il sorgente dell'app dentro la cartella indicata.
  local destinazione="$1"
  mkdir -p "$destinazione"
  # Le schermate pesano più dell'app: restano nel repository, dove si
  # guardano, e non nell'archivio che ognuno scarica.
  cp -r ricerca pyproject.toml README.md LICENSE "$destinazione/"
  find "$destinazione" -name '__pycache__' -type d -prune -exec rm -rf {} +
}

# ── Linux: sorgente, lanciatore, scorciatoia per il menu ──────────────
LINUX="$LAVORO/linux/ricerca"
sorgente_in "$LINUX"
cp start.sh "$LINUX/"
cp packaging/install-shortcut-linux.sh "$LINUX/"
tar -czf "$DIST/ricerca-$VERSIONE-linux.tar.gz" -C "$LAVORO/linux" ricerca

# ── macOS: un vero bundle, si apre senza finestra di Terminale ────────
MAC="$LAVORO/macos"
BUNDLE="$MAC/Ricerca.app/Contents"
mkdir -p "$BUNDLE/MacOS" "$BUNDLE/Resources"
sorgente_in "$BUNDLE/Resources/app"
cp packaging/macos/launch "$BUNDLE/MacOS/Ricerca"
chmod +x "$BUNDLE/MacOS/Ricerca"
cp packaging/Ricerca.icns "$BUNDLE/Resources/Ricerca.icns"
sed "s/__VERSIONE__/$VERSIONE/g" packaging/macos/Info.plist > "$BUNDLE/Info.plist"
# Copia dell'unico lanciatore: un secondo file resterebbe indietro.
cp start.sh "$MAC/start-from-terminal.command"
chmod +x "$MAC/start-from-terminal.command"
cat > "$MAC/READ-ME-FIRST.txt" <<'FINE'
Ricerca — installing on macOS

1. Drag Ricerca.app into your Applications folder.
2. First launch: right-click the icon → Open → Open.
   Needed because the app is not signed with an Apple Developer ID.
   If macOS calls it “damaged”, run this once in Terminal:
       xattr -dr com.apple.quarantine /Applications/Ricerca.app
3. After that a double-click is enough: the browser opens, no Terminal.
   Closing the page quits the app.

---

Ricerca — installazione su macOS

1. Trascina Ricerca.app nella cartella Applicazioni.
2. Al primo avvio: clic destro sull'icona → Apri → Apri.
   Serve perché l'app non è firmata con un Developer ID Apple.
   Se macOS la dice «danneggiata», apri il Terminale una volta sola:
       xattr -dr com.apple.quarantine /Applications/Ricerca.app
3. Poi basta il doppio clic: si apre il browser, senza Terminale.
   Chiudendo la pagina l'app si chiude da sola.

Il primo avvio scarica uv e l'interprete Python in ~/.ricerca
(serve la connessione a internet). Il registro sta in ~/.ricerca/avvio.log.
FINE
tar -czf "$DIST/ricerca-$VERSIONE-macos.tar.gz" -C "$MAC" Ricerca.app start-from-terminal.command READ-ME-FIRST.txt

# ── Windows: sorgente, .bat, icona e creatore di collegamento ─────────
WIN="$LAVORO/windows/ricerca"
sorgente_in "$WIN"
cp start.bat "$WIN/"
cp packaging/Ricerca.ico "$WIN/"
cp packaging/create-shortcut-windows.bat "$WIN/"
( cd "$LAVORO/windows" && zip -qr "../../ricerca-$VERSIONE-windows.zip" ricerca )

rm -rf "$LAVORO"
ls -lh "$DIST"
