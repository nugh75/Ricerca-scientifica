# LitReview

A literature-review desktop assistant: search across multiple scholarly
sources, collect PDFs in a local library, analyze papers with DeepSeek,
and export BibTeX.

## Status

- **Backend** (Python/FastAPI sidecar): complete — 115 tests green, shipped
  as one-click GitHub releases. See [backend/README.md](backend/README.md).
- **Desktop shell** (Tauri): planned. The backend is designed to run as a
  sidecar (`externalBin`); see
  [docs/superpowers/specs/2026-08-17-literature-review-app-design.md](docs/superpowers/specs/2026-08-17-literature-review-app-design.md).

## One-click install (end users)

From the [latest release](https://github.com/nugh75/Ricerca-scientifica/releases),
download the launcher for your system and double-click it:

| OS | Launcher | Notes |
|---|---|---|
| Windows | `litreview.bat` | no Python required |
| macOS | `litreview-macos.dmg` | Apple Silicon (arm64) only; open the dmg, see note below |
| Linux | `litreview-unix.sh` | run `chmod +x litreview-unix.sh` first |

**macOS note:** open the `.dmg` and run `litreview.command` from the mounted
volume (or drag it out first). The file inside the dmg keeps its execute
bit, but Gatekeeper still quarantines anything downloaded from the internet,
so on first launch use Ctrl-click → "Open" instead of a plain double-click.
(Proper signing/notarization would remove this step; it requires an Apple
Developer ID and is planned as future hardening.) The launcher then
downloads the frozen backend and starts it — everything runs locally,
bound to `127.0.0.1`, with keys only in the system keyring.

The launcher downloads the latest frozen backend into `~/.litreview/bin/`,
starts the server on `127.0.0.1:8756`, and opens the API UI
(`/docs`). Re-running always updates to the latest release. API keys are
configured from the Settings endpoints and stored in the system keyring.

## Features

- Multi-source search: OpenAlex, Semantic Scholar, Crossref, DOAJ — with
  cross-source deduplication and per-source error isolation.
- Local SQLite library; PDF download from open-access links or manual upload.
- DeepSeek analysis: summary, metadata extraction, citation verification,
  and multi-turn chat over the paper text.
- BibTeX export with generated cite keys.
- Keys only in the OS keyring; server binds to localhost only.

## Development

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -v                 # 115 tests
.venv/bin/uvicorn litreview.main:app --host 127.0.0.1 --port 8756 --reload
```

Frozen builds per OS are produced in CI on every `v*` tag
(`.github/workflows/release.yml`); locally you can build the Linux binary
with `pyinstaller --distpath dist --workpath build packaging/litreview.spec`.

## Repository layout

- `backend/` — FastAPI service, tests, PyInstaller packaging, launchers.
- `docs/superpowers/` — design specs and implementation plans (SDD workflow).
