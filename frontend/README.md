# LitReview desktop frontend

Tauri shell around the LitReview backend (`../backend`).

## Local development

1. Build the backend binary once (or after backend changes):
   ```bash
   cd ../backend
   pip install -e ".[dev]" pyinstaller
   pyinstaller --distpath dist --workpath build packaging/litreview.spec
   ```
2. Stage it as the Tauri sidecar:
   ```bash
   cd ../frontend
   npm run prepare-sidecar
   ```
3. Run the app:
   ```bash
   npm install
   npm run dev:desktop   # or: npm run tauri dev
   ```

Backend runs fixed on `http://127.0.0.1:8756` — see `../backend/src/litreview/__main__.py`. No configuration needed.

## Running under WSL2 (Windows Subsystem for Linux)

The desktop shell needs a display server. Under WSL2 the display is provided by
**WSLg** (weston + Xwayland), but its environment variables (`DISPLAY`,
`WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`) are only
injected into login shells. In SSH sessions and many IDE terminals they are
missing, so GTK fails to initialize and the app dies immediately with:

```
Failed to initialize gtk backend!: BoolError { message: "Failed to initialize GTK", ... }
```

`npm run dev:desktop` runs `scripts/tauri-dev.sh`, which detects WSL and
restores the WSLg variables before launching the app. If the window still does
not appear:

- WSLg may be stopped — on Windows run `wsl --shutdown`, reopen the terminal and retry.
- Headless fallback (no visible window, useful for CI/smoke tests):
  ```bash
  xvfb-run -a npm run tauri dev
  ```
- On a plain Linux desktop (no WSL), just set `DISPLAY` as usual and run
  `npm run tauri dev` directly.
