#!/usr/bin/env python3
"""Disegna l'icona dell'app e ne costruisce le versioni per ogni sistema.

Il disegno è HTML: viene reso con il Chromium di Playwright e ritagliato alle
misure che servono. Da qui escono `ricerca/static/icona.png` (favicon e
scorciatoia Linux) e `packaging/Ricerca.icns` (bundle macOS).

Si esegue a mano quando l'icona cambia: i file prodotti stanno nel
repository, così né la CI né chi installa hanno bisogno di un browser.

    uv run --with playwright python scripts/crea-icona.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RADICE = Path(__file__).resolve().parent.parent
CHROME = Path.home() / ".cache/ms-playwright/chromium-1228/chrome-linux64/chrome"

DISEGNO = """
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&display=swap">
<style>
  html, body { margin: 0; width: 1024px; height: 1024px; }
  .icona {
    width: 1024px; height: 1024px; box-sizing: border-box;
    background: #e9ece6; display: grid; place-items: center; position: relative;
    font-family: Fraunces, Georgia, serif;
  }
  /* la rigatura della carta, come nell'app */
  .righe { position: absolute; inset: 0;
    background: repeating-linear-gradient(#e9ece6 0 78px, #cfd6cd 78px 82px); opacity: .55; }
  .marca {
    position: relative; width: 620px; height: 620px; background: #c9e265;
    border: 26px solid #16262b; display: grid; place-items: center;
  }
  .marca span { font-size: 430px; line-height: 1; color: #16262b; margin-top: -30px; }
</style></head>
<body><div class="icona"><div class="righe"></div>
  <div class="marca"><span>R</span></div>
</div></body></html>
"""

MISURE_ICNS = {
    "ic07": 128,
    "ic08": 256,
    "ic09": 512,
    "ic10": 1024,
    "ic11": 32,
    "ic12": 64,
    "ic13": 256,
    "ic14": 512,
}


def rendi(misure: list[int]) -> dict[int, bytes]:
    """Una PNG per ogni misura richiesta."""

    immagini: dict[int, bytes] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=str(CHROME) if CHROME.exists() else None
        )
        for misura in sorted(set(misure)):
            page = browser.new_page(
                viewport={"width": 1024, "height": 1024},
                device_scale_factor=misura / 1024,
            )
            page.set_content(DISEGNO, wait_until="networkidle")
            immagini[misura] = page.screenshot(omit_background=False)
            page.close()
        browser.close()
    return immagini


def scrivi_icns(immagini: dict[int, bytes], destinazione: Path) -> None:
    """Un file .icns è una serie di blocchi «tipo + lunghezza + PNG»."""

    blocchi = b""
    for tipo, misura in MISURE_ICNS.items():
        dati = immagini[misura]
        blocchi += tipo.encode("ascii") + struct.pack(">I", len(dati) + 8) + dati
    destinazione.write_bytes(b"icns" + struct.pack(">I", len(blocchi) + 8) + blocchi)


def scrivi_ico(immagini: dict[int, bytes], destinazione: Path) -> None:
    """ICO con PNG dentro: Windows lo accetta da Vista in poi."""

    misure = [256, 64, 32]
    intestazione = struct.pack("<HHH", 0, 1, len(misure))
    offset = len(intestazione) + 16 * len(misure)
    voci, corpo = b"", b""
    for misura in misure:
        dati = immagini[misura]
        larghezza = 0 if misura >= 256 else misura
        voci += struct.pack(
            "<BBBBHHII", larghezza, larghezza, 0, 0, 1, 32, len(dati), offset
        )
        corpo += dati
        offset += len(dati)
    destinazione.write_bytes(intestazione + voci + corpo)


def main() -> int:
    misure = sorted(set(MISURE_ICNS.values()) | {512, 64, 32})
    immagini = rendi(misure)

    png = RADICE / "ricerca/static/icona.png"
    png.write_bytes(immagini[512])

    icns = RADICE / "packaging/Ricerca.icns"
    icns.parent.mkdir(parents=True, exist_ok=True)
    scrivi_icns(immagini, icns)

    ico = RADICE / "packaging/Ricerca.ico"
    scrivi_ico(immagini, ico)

    for file in (png, icns, ico):
        print(f"{file} ({file.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
