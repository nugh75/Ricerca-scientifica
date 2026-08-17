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
   npm run tauri dev
   ```

Backend runs fixed on `http://127.0.0.1:8756` — see `../backend/src/litreview/__main__.py`. No configuration needed.
