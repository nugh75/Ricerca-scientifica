# LitReview Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Python/FastAPI backend for the literature-review desktop
app: multi-source search (OpenAlex, Semantic Scholar, Crossref, DOAJ), PDF
download/upload/text-extraction, DeepSeek-based analysis (summary, metadata
extraction, chat Q&A, bib verification), local SQLite library, and `.bib`
export — as a standalone, fully tested FastAPI service.

**Architecture:** A single Python package (`litreview`) exposing normalized
search-client modules, a SQLite persistence layer accessed through a FastAPI
dependency, an OS-keyring-backed key store, a DeepSeek client wrapper, and
FastAPI routers that compose these into HTTP endpoints. The service runs
standalone via `uvicorn` for this plan; a later plan wires it as a Tauri
sidecar behind a desktop UI.

**Tech Stack:** Python ≥3.11, FastAPI, uvicorn, pydantic, requests, pypdf,
keyring, openai SDK (pointed at DeepSeek's OpenAI-compatible endpoint),
pytest, httpx (test client transport), fpdf2 (test-only, to generate PDF
fixtures).

**Spec:** `docs/superpowers/specs/2026-08-17-literature-review-app-design.md`

**Scope note:** This plan covers ONLY the backend subsystem. It is
independently useful and testable (run via `uvicorn litreview.main:app` and
call with `curl`/`httpx`). The Tauri shell, frontend UI, onboarding wizard,
and cross-platform installer packaging are a separate subsystem with
different tooling (Rust/Node) and will get their own follow-up plan once
this backend is complete and merged.

## Global Constraints

- Python ≥3.11 for all backend code.
- All backend code lives under `backend/src/litreview/`; all tests under
  `backend/tests/`. Run tests from `backend/`: `pytest`.
- API keys are NEVER written to disk in plaintext — only through the
  `keyring` library (`keys.py`).
- DeepSeek client uses base_url `https://api.deepseek.com`, model
  `deepseek-chat` (both as named constants in `config.py`, not hardcoded
  elsewhere).
- PDF text extraction uses `pypdf` only (pure Python, no system-level
  dependency) — required so the binary can later be frozen with PyInstaller
  without bundling native libraries.
- Every task ends with a green `pytest` run and a commit. Commit messages
  use prefix `feat(backend): ...`.
- No placeholders, no TODOs left in code — every function is fully
  implemented as specified in this plan.

---

### Task 1: Project scaffolding, config, SQLite layer

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/litreview/__init__.py`
- Create: `backend/src/litreview/config.py`
- Create: `backend/src/litreview/db.py`
- Test: `backend/tests/conftest.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Produces: `config.APP_DIR: Path`, `config.DB_PATH: Path`,
  `config.PDF_DIR: Path`, `config.KEYRING_SERVICE: str`,
  `config.DEEPSEEK_BASE_URL: str`, `config.DEEPSEEK_MODEL: str`
- Produces: `db.SCHEMA: str`, `db.get_connection(db_path: Path | None = None) -> sqlite3.Connection`,
  `db.get_db() -> Generator[sqlite3.Connection, None, None]` (FastAPI dependency)
- Produces (test fixtures): `conftest.tmp_db_path`, `conftest.conn`

- [ ] **Step 1: Create the package scaffolding and config**

`backend/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "litreview-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "pydantic>=2.6",
    "requests>=2.31",
    "pypdf>=4.0",
    "keyring>=25.0",
    "openai>=1.30",
]

[project.optional-dependencies]
dev = ["pytest>=7.4", "httpx>=0.27", "fpdf2>=2.7"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

`backend/src/litreview/__init__.py`:

```python
```

(empty file — marks the package)

`backend/src/litreview/config.py`:

```python
from pathlib import Path

APP_DIR = Path.home() / ".litreview"
DB_PATH = APP_DIR / "library.db"
PDF_DIR = APP_DIR / "pdfs"
KEYRING_SERVICE = "litreview"

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
```

- [ ] **Step 2: Write the DB layer**

`backend/src/litreview/db.py`:

```python
import sqlite3
from pathlib import Path
from typing import Generator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    authors TEXT NOT NULL,
    year INTEGER,
    doi TEXT,
    source TEXT,
    abstract TEXT,
    oa_pdf_url TEXT,
    pdf_path TEXT,
    extracted_text_ok INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    bib_key TEXT,
    analysis_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    messages_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
```

- [ ] **Step 3: Write conftest fixtures and the DB test**

`backend/tests/conftest.py`:

```python
import pytest


@pytest.fixture
def tmp_db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def conn(tmp_db_path):
    from litreview import db as db_module

    connection = db_module.get_connection(tmp_db_path)
    yield connection
    connection.close()
```

`backend/tests/test_db.py`:

```python
from litreview import config
from litreview import db as db_module


def test_get_connection_creates_all_tables(tmp_db_path):
    conn = db_module.get_connection(tmp_db_path)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"articles", "chat_sessions", "settings"} <= tables
    conn.close()


def test_get_connection_creates_parent_dir(tmp_path):
    nested = tmp_path / "nested" / "dir" / "lib.db"
    conn = db_module.get_connection(nested)
    assert nested.exists()
    conn.close()


def test_get_db_yields_working_connection_and_closes(tmp_db_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_db_path)
    gen = db_module.get_db()
    conn = next(gen)
    conn.execute("SELECT 1")
    try:
        next(gen)
    except StopIteration:
        pass
    else:
        raise AssertionError("generator should stop after one yield")
```

- [ ] **Step 4: Install and run tests, verify they pass**

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -v
```

Expected: all tests in `test_db.py` PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/src/litreview/__init__.py \
        backend/src/litreview/config.py backend/src/litreview/db.py \
        backend/tests/conftest.py backend/tests/test_db.py
git commit -m "feat(backend): scaffold package, config, and SQLite layer"
```

---

### Task 2: API key storage (keyring)

**Files:**
- Create: `backend/src/litreview/keys.py`
- Test: `backend/tests/test_keys.py`

**Interfaces:**
- Consumes: `config.KEYRING_SERVICE`
- Produces: `keys.KNOWN_KEYS: list[str]`, `keys.KeyringUnavailableError`,
  `keys.set_key(name: str, value: str) -> None`,
  `keys.get_key(name: str) -> str | None`,
  `keys.delete_key(name: str) -> None`,
  `keys.has_key(name: str) -> bool`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_keys.py`:

```python
import keyring.errors
import pytest

from litreview import keys


class FakeKeyringBackend:
    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}

    def set_password(self, service, name, value):
        self.store[(service, name)] = value

    def get_password(self, service, name):
        return self.store.get((service, name))

    def delete_password(self, service, name):
        if (service, name) not in self.store:
            raise keyring.errors.PasswordDeleteError("not found")
        del self.store[(service, name)]


@pytest.fixture
def fake_backend(monkeypatch):
    backend = FakeKeyringBackend()
    monkeypatch.setattr(keys.keyring, "set_password", backend.set_password)
    monkeypatch.setattr(keys.keyring, "get_password", backend.get_password)
    monkeypatch.setattr(keys.keyring, "delete_password", backend.delete_password)
    return backend


def test_set_and_get_key_roundtrip(fake_backend):
    keys.set_key("deepseek_api_key", "sk-test-123")
    assert keys.get_key("deepseek_api_key") == "sk-test-123"


def test_get_key_returns_none_when_missing(fake_backend):
    assert keys.get_key("deepseek_api_key") is None


def test_has_key_true_after_set(fake_backend):
    keys.set_key("openalex_mailto", "me@example.org")
    assert keys.has_key("openalex_mailto") is True


def test_has_key_false_when_missing(fake_backend):
    assert keys.has_key("openalex_mailto") is False


def test_delete_key_removes_value(fake_backend):
    keys.set_key("crossref_mailto", "me@example.org")
    keys.delete_key("crossref_mailto")
    assert keys.get_key("crossref_mailto") is None


def test_delete_key_missing_does_not_raise(fake_backend):
    keys.delete_key("crossref_mailto")  # no error even if never set


def test_unknown_key_name_raises_value_error(fake_backend):
    with pytest.raises(ValueError):
        keys.set_key("not_a_real_key", "x")
    with pytest.raises(ValueError):
        keys.get_key("not_a_real_key")


def test_set_key_wraps_no_keyring_error(monkeypatch):
    def raise_no_keyring(*args, **kwargs):
        raise keyring.errors.NoKeyringError("no backend")

    monkeypatch.setattr(keys.keyring, "set_password", raise_no_keyring)
    with pytest.raises(keys.KeyringUnavailableError):
        keys.set_key("deepseek_api_key", "sk-test")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_keys.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'litreview.keys'`

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/keys.py`:

```python
import keyring
import keyring.errors

from .config import KEYRING_SERVICE

KNOWN_KEYS = [
    "openalex_mailto",
    "semantic_scholar_key",
    "crossref_mailto",
    "deepseek_api_key",
]


class KeyringUnavailableError(Exception):
    pass


def _validate(name: str) -> None:
    if name not in KNOWN_KEYS:
        raise ValueError(f"unknown key name: {name}")


def set_key(name: str, value: str) -> None:
    _validate(name)
    try:
        keyring.set_password(KEYRING_SERVICE, name, value)
    except keyring.errors.NoKeyringError as e:
        raise KeyringUnavailableError(
            "Nessun keyring di sistema disponibile. Su Linux installa e avvia "
            "gnome-keyring o un servizio Secret Service compatibile."
        ) from e


def get_key(name: str) -> str | None:
    _validate(name)
    try:
        return keyring.get_password(KEYRING_SERVICE, name)
    except keyring.errors.NoKeyringError as e:
        raise KeyringUnavailableError(
            "Nessun keyring di sistema disponibile. Su Linux installa e avvia "
            "gnome-keyring o un servizio Secret Service compatibile."
        ) from e


def delete_key(name: str) -> None:
    _validate(name)
    try:
        keyring.delete_password(KEYRING_SERVICE, name)
    except keyring.errors.PasswordDeleteError:
        pass


def has_key(name: str) -> bool:
    return bool(get_key(name))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_keys.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/keys.py backend/tests/test_keys.py
git commit -m "feat(backend): add keyring-backed API key storage"
```

---

### Task 3: API client base + OpenAlex client

**Files:**
- Create: `backend/src/litreview/api_clients/__init__.py`
- Create: `backend/src/litreview/api_clients/base.py`
- Create: `backend/src/litreview/api_clients/openalex.py`
- Test: `backend/tests/test_api_clients_openalex.py`

**Interfaces:**
- Produces: `base.NormalizedResult` (dataclass: `title: str, authors: list[str],
  year: int | None, doi: str | None, source: str, abstract: str | None = None,
  oa_pdf_url: str | None = None`)
- Produces: `base.SourceError(source: str, message: str)` (Exception,
  attributes `.source`, `.message`)
- Produces: `openalex.search(query: str, *, mailto: str | None = None, per_page: int = 10) -> list[NormalizedResult]`

- [ ] **Step 1: Write the failing test**

`backend/src/litreview/api_clients/__init__.py`:

```python
```

(empty file)

`backend/tests/test_api_clients_openalex.py`:

```python
from unittest.mock import Mock, patch

import requests

from litreview.api_clients import openalex
from litreview.api_clients.base import SourceError

SAMPLE_RESPONSE = {
    "results": [
        {
            "title": "A Study of Something",
            "authorships": [
                {"author": {"display_name": "Jane Smith"}},
                {"author": {"display_name": "John Doe"}},
            ],
            "publication_year": 2021,
            "doi": "https://doi.org/10.1/abc",
            "open_access": {"oa_url": "https://example.org/paper.pdf"},
        }
    ]
}


def test_search_normalizes_results():
    mock_resp = Mock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status.return_value = None
    with patch.object(openalex.requests, "get", return_value=mock_resp) as mock_get:
        results = openalex.search("something", mailto="me@example.org")

    assert len(results) == 1
    r = results[0]
    assert r.title == "A Study of Something"
    assert r.authors == ["Jane Smith", "John Doe"]
    assert r.year == 2021
    assert r.doi == "https://doi.org/10.1/abc"
    assert r.source == "openalex"
    assert r.oa_pdf_url == "https://example.org/paper.pdf"

    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["mailto"] == "me@example.org"


def test_search_omits_mailto_when_not_given():
    mock_resp = Mock()
    mock_resp.json.return_value = {"results": []}
    mock_resp.raise_for_status.return_value = None
    with patch.object(openalex.requests, "get", return_value=mock_resp) as mock_get:
        openalex.search("something")
    assert "mailto" not in mock_get.call_args.kwargs["params"]


def test_search_raises_source_error_on_request_exception():
    with patch.object(
        openalex.requests, "get", side_effect=requests.RequestException("timeout")
    ):
        try:
            openalex.search("something")
        except SourceError as e:
            assert e.source == "openalex"
        else:
            raise AssertionError("expected SourceError")


def test_search_handles_missing_optional_fields():
    mock_resp = Mock()
    mock_resp.json.return_value = {"results": [{"title": "No extras"}]}
    mock_resp.raise_for_status.return_value = None
    with patch.object(openalex.requests, "get", return_value=mock_resp):
        results = openalex.search("x")
    assert results[0].authors == []
    assert results[0].year is None
    assert results[0].doi is None
    assert results[0].oa_pdf_url is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_api_clients_openalex.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'litreview.api_clients'`

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/api_clients/base.py`:

```python
from dataclasses import dataclass


@dataclass
class NormalizedResult:
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    source: str
    abstract: str | None = None
    oa_pdf_url: str | None = None


class SourceError(Exception):
    def __init__(self, source: str, message: str):
        self.source = source
        self.message = message
        super().__init__(f"{source}: {message}")
```

`backend/src/litreview/api_clients/openalex.py`:

```python
import requests

from .base import NormalizedResult, SourceError

API_URL = "https://api.openalex.org/works"


def search(
    query: str, *, mailto: str | None = None, per_page: int = 10
) -> list[NormalizedResult]:
    params: dict = {"search": query, "per-page": per_page}
    if mailto:
        params["mailto"] = mailto
    try:
        r = requests.get(API_URL, params=params, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        raise SourceError("openalex", str(e)) from e

    data = r.json()
    results = []
    for item in data.get("results", []):
        authors = [
            (a.get("author") or {}).get("display_name", "")
            for a in item.get("authorships", [])
        ]
        oa = item.get("open_access") or {}
        results.append(
            NormalizedResult(
                title=item.get("title") or "",
                authors=[a for a in authors if a],
                year=item.get("publication_year"),
                doi=item.get("doi"),
                source="openalex",
                abstract=None,
                oa_pdf_url=oa.get("oa_url"),
            )
        )
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_api_clients_openalex.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/api_clients/__init__.py \
        backend/src/litreview/api_clients/base.py \
        backend/src/litreview/api_clients/openalex.py \
        backend/tests/test_api_clients_openalex.py
git commit -m "feat(backend): add API client base types and OpenAlex client"
```

---

### Task 4: Semantic Scholar client

**Files:**
- Create: `backend/src/litreview/api_clients/semantic_scholar.py`
- Test: `backend/tests/test_api_clients_semantic_scholar.py`

**Interfaces:**
- Consumes: `base.NormalizedResult`, `base.SourceError`
- Produces: `semantic_scholar.search(query: str, *, api_key: str | None = None, per_page: int = 10) -> list[NormalizedResult]`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_api_clients_semantic_scholar.py`:

```python
from unittest.mock import Mock, patch

import requests

from litreview.api_clients import semantic_scholar
from litreview.api_clients.base import SourceError

SAMPLE_RESPONSE = {
    "data": [
        {
            "title": "Deep Learning Basics",
            "authors": [{"name": "Ada Lovelace"}, {"name": "Alan Turing"}],
            "year": 2019,
            "externalIds": {"DOI": "10.2/xyz"},
            "abstract": "An intro to deep learning.",
            "openAccessPdf": {"url": "https://example.org/dl.pdf"},
        }
    ]
}


def test_search_normalizes_results():
    mock_resp = Mock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status.return_value = None
    with patch.object(
        semantic_scholar.requests, "get", return_value=mock_resp
    ) as mock_get:
        results = semantic_scholar.search("deep learning", api_key="ss-key")

    assert len(results) == 1
    r = results[0]
    assert r.title == "Deep Learning Basics"
    assert r.authors == ["Ada Lovelace", "Alan Turing"]
    assert r.year == 2019
    assert r.doi == "10.2/xyz"
    assert r.source == "semantic_scholar"
    assert r.abstract == "An intro to deep learning."
    assert r.oa_pdf_url == "https://example.org/dl.pdf"
    assert mock_get.call_args.kwargs["headers"]["x-api-key"] == "ss-key"


def test_search_without_api_key_sends_no_header():
    mock_resp = Mock()
    mock_resp.json.return_value = {"data": []}
    mock_resp.raise_for_status.return_value = None
    with patch.object(semantic_scholar.requests, "get", return_value=mock_resp) as mock_get:
        semantic_scholar.search("x")
    assert mock_get.call_args.kwargs["headers"] == {}


def test_search_raises_source_error_on_request_exception():
    with patch.object(
        semantic_scholar.requests, "get", side_effect=requests.RequestException("boom")
    ):
        try:
            semantic_scholar.search("x")
        except SourceError as e:
            assert e.source == "semantic_scholar"
        else:
            raise AssertionError("expected SourceError")


def test_search_handles_missing_optional_fields():
    mock_resp = Mock()
    mock_resp.json.return_value = {"data": [{"title": "Bare"}]}
    mock_resp.raise_for_status.return_value = None
    with patch.object(semantic_scholar.requests, "get", return_value=mock_resp):
        results = semantic_scholar.search("x")
    assert results[0].authors == []
    assert results[0].doi is None
    assert results[0].oa_pdf_url is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_api_clients_semantic_scholar.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'litreview.api_clients.semantic_scholar'`

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/api_clients/semantic_scholar.py`:

```python
import requests

from .base import NormalizedResult, SourceError

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,authors,year,externalIds,abstract,openAccessPdf"


def search(
    query: str, *, api_key: str | None = None, per_page: int = 10
) -> list[NormalizedResult]:
    params = {"query": query, "limit": per_page, "fields": FIELDS}
    headers = {"x-api-key": api_key} if api_key else {}
    try:
        r = requests.get(API_URL, params=params, headers=headers, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        raise SourceError("semantic_scholar", str(e)) from e

    data = r.json()
    results = []
    for item in data.get("data", []):
        oa_pdf = item.get("openAccessPdf") or {}
        results.append(
            NormalizedResult(
                title=item.get("title") or "",
                authors=[a.get("name", "") for a in item.get("authors", []) if a.get("name")],
                year=item.get("year"),
                doi=(item.get("externalIds") or {}).get("DOI"),
                source="semantic_scholar",
                abstract=item.get("abstract"),
                oa_pdf_url=oa_pdf.get("url"),
            )
        )
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_api_clients_semantic_scholar.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/api_clients/semantic_scholar.py \
        backend/tests/test_api_clients_semantic_scholar.py
git commit -m "feat(backend): add Semantic Scholar client"
```

---

### Task 5: Crossref client

**Files:**
- Create: `backend/src/litreview/api_clients/crossref.py`
- Test: `backend/tests/test_api_clients_crossref.py`

**Interfaces:**
- Consumes: `base.NormalizedResult`, `base.SourceError`
- Produces: `crossref.search(query: str, *, mailto: str | None = None, per_page: int = 10) -> list[NormalizedResult]`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_api_clients_crossref.py`:

```python
from unittest.mock import Mock, patch

import requests

from litreview.api_clients import crossref
from litreview.api_clients.base import SourceError

SAMPLE_RESPONSE = {
    "message": {
        "items": [
            {
                "title": ["On Networks"],
                "author": [{"given": "Grace", "family": "Hopper"}],
                "issued": {"date-parts": [[2018, 5]]},
                "DOI": "10.3/net",
                "abstract": "<jats:p>About networks.</jats:p>",
            }
        ]
    }
}


def test_search_normalizes_results():
    mock_resp = Mock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status.return_value = None
    with patch.object(crossref.requests, "get", return_value=mock_resp) as mock_get:
        results = crossref.search("networks", mailto="me@example.org")

    assert len(results) == 1
    r = results[0]
    assert r.title == "On Networks"
    assert r.authors == ["Grace Hopper"]
    assert r.year == 2018
    assert r.doi == "10.3/net"
    assert r.source == "crossref"
    assert "me@example.org" in mock_get.call_args.kwargs["headers"]["User-Agent"]


def test_search_raises_source_error_on_request_exception():
    with patch.object(
        crossref.requests, "get", side_effect=requests.RequestException("down")
    ):
        try:
            crossref.search("x")
        except SourceError as e:
            assert e.source == "crossref"
        else:
            raise AssertionError("expected SourceError")


def test_search_handles_missing_optional_fields():
    mock_resp = Mock()
    mock_resp.json.return_value = {"message": {"items": [{}]}}
    mock_resp.raise_for_status.return_value = None
    with patch.object(crossref.requests, "get", return_value=mock_resp):
        results = crossref.search("x")
    assert results[0].title == ""
    assert results[0].authors == []
    assert results[0].year is None
    assert results[0].doi is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_api_clients_crossref.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'litreview.api_clients.crossref'`

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/api_clients/crossref.py`:

```python
import requests

from .base import NormalizedResult, SourceError

API_URL = "https://api.crossref.org/works"


def search(
    query: str, *, mailto: str | None = None, per_page: int = 10
) -> list[NormalizedResult]:
    params = {"query": query, "rows": per_page}
    ua = "litreview/1.0"
    if mailto:
        ua += f" (mailto:{mailto})"
    headers = {"User-Agent": ua}
    try:
        r = requests.get(API_URL, params=params, headers=headers, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        raise SourceError("crossref", str(e)) from e

    data = r.json()
    items = (data.get("message") or {}).get("items", [])
    results = []
    for item in items:
        title_list = item.get("title") or [""]
        authors = []
        for a in item.get("author", []) or []:
            name = " ".join(filter(None, [a.get("given"), a.get("family")]))
            if name:
                authors.append(name)
        year = None
        date_parts = (item.get("issued") or {}).get("date-parts")
        if date_parts and date_parts[0]:
            year = date_parts[0][0]
        results.append(
            NormalizedResult(
                title=title_list[0],
                authors=authors,
                year=year,
                doi=item.get("DOI"),
                source="crossref",
                abstract=item.get("abstract"),
                oa_pdf_url=None,
            )
        )
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_api_clients_crossref.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/api_clients/crossref.py \
        backend/tests/test_api_clients_crossref.py
git commit -m "feat(backend): add Crossref client"
```

---

### Task 6: DOAJ client

**Files:**
- Create: `backend/src/litreview/api_clients/doaj.py`
- Test: `backend/tests/test_api_clients_doaj.py`

**Interfaces:**
- Consumes: `base.NormalizedResult`, `base.SourceError`
- Produces: `doaj.search(query: str, *, per_page: int = 10) -> list[NormalizedResult]`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_api_clients_doaj.py`:

```python
from unittest.mock import Mock, patch

import requests

from litreview.api_clients import doaj
from litreview.api_clients.base import SourceError

SAMPLE_RESPONSE = {
    "results": [
        {
            "bibjson": {
                "title": "Open Access Study",
                "author": [{"name": "Rosa Park"}],
                "year": "2022",
                "abstract": "About open access.",
                "identifier": [{"type": "doi", "id": "10.4/oa"}],
                "link": [{"type": "fulltext", "url": "https://example.org/oa.pdf"}],
            }
        }
    ]
}


def test_search_normalizes_results():
    mock_resp = Mock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status.return_value = None
    with patch.object(doaj.requests, "get", return_value=mock_resp):
        results = doaj.search("open access")

    assert len(results) == 1
    r = results[0]
    assert r.title == "Open Access Study"
    assert r.authors == ["Rosa Park"]
    assert r.year == 2022
    assert r.doi == "10.4/oa"
    assert r.source == "doaj"
    assert r.oa_pdf_url == "https://example.org/oa.pdf"


def test_search_raises_source_error_on_request_exception():
    with patch.object(
        doaj.requests, "get", side_effect=requests.RequestException("timeout")
    ):
        try:
            doaj.search("x")
        except SourceError as e:
            assert e.source == "doaj"
        else:
            raise AssertionError("expected SourceError")


def test_search_handles_missing_optional_fields():
    mock_resp = Mock()
    mock_resp.json.return_value = {"results": [{"bibjson": {}}]}
    mock_resp.raise_for_status.return_value = None
    with patch.object(doaj.requests, "get", return_value=mock_resp):
        results = doaj.search("x")
    assert results[0].title == ""
    assert results[0].authors == []
    assert results[0].year is None
    assert results[0].doi is None
    assert results[0].oa_pdf_url is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_api_clients_doaj.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'litreview.api_clients.doaj'`

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/api_clients/doaj.py`:

```python
import requests

from .base import NormalizedResult, SourceError

API_URL = "https://doaj.org/api/search/articles/{query}"


def search(query: str, *, per_page: int = 10) -> list[NormalizedResult]:
    url = API_URL.format(query=requests.utils.quote(query, safe=""))
    try:
        r = requests.get(url, params={"pageSize": per_page}, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        raise SourceError("doaj", str(e)) from e

    data = r.json()
    results = []
    for item in data.get("results", []):
        bibjson = item.get("bibjson") or {}
        authors = [a.get("name", "") for a in bibjson.get("author", []) or [] if a.get("name")]
        doi = None
        for ident in bibjson.get("identifier", []) or []:
            if ident.get("type") == "doi":
                doi = ident.get("id")
        pdf_url = None
        for link in bibjson.get("link", []) or []:
            if link.get("type") == "fulltext":
                pdf_url = link.get("url")
        year_raw = bibjson.get("year")
        results.append(
            NormalizedResult(
                title=bibjson.get("title") or "",
                authors=authors,
                year=int(year_raw) if year_raw else None,
                doi=doi,
                source="doaj",
                abstract=bibjson.get("abstract"),
                oa_pdf_url=pdf_url,
            )
        )
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_api_clients_doaj.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/api_clients/doaj.py backend/tests/test_api_clients_doaj.py
git commit -m "feat(backend): add DOAJ client"
```

---

### Task 7: Result deduplication/merge

**Files:**
- Create: `backend/src/litreview/dedup.py`
- Test: `backend/tests/test_dedup.py`

**Interfaces:**
- Consumes: `api_clients.base.NormalizedResult`
- Produces: `dedup.merge_results(results_by_source: dict[str, list[NormalizedResult]], threshold: float = 0.85) -> list[NormalizedResult]`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_dedup.py`:

```python
from litreview.api_clients.base import NormalizedResult
from litreview.dedup import merge_results


def _r(title, doi=None, source="s", oa_pdf_url=None, abstract=None):
    return NormalizedResult(
        title=title, authors=["A"], year=2020, doi=doi, source=source,
        abstract=abstract, oa_pdf_url=oa_pdf_url,
    )


def test_merge_keeps_distinct_results():
    by_source = {
        "openalex": [_r("Paper One", doi="10.1/a")],
        "crossref": [_r("Completely Different Paper", doi="10.2/b")],
    }
    merged = merge_results(by_source)
    assert len(merged) == 2


def test_merge_dedupes_by_doi_case_insensitive():
    by_source = {
        "openalex": [_r("Paper One", doi="10.1/ABC")],
        "crossref": [_r("Paper One (slightly different title)", doi="10.1/abc")],
    }
    merged = merge_results(by_source)
    assert len(merged) == 1


def test_merge_dedupes_by_title_similarity_without_doi():
    by_source = {
        "openalex": [_r("A Study of Neural Networks")],
        "crossref": [_r("A Study of Neural Networks.")],
    }
    merged = merge_results(by_source)
    assert len(merged) == 1


def test_merge_fills_missing_oa_pdf_url_from_later_source():
    by_source = {
        "openalex": [_r("Paper One", doi="10.1/a", oa_pdf_url=None)],
        "doaj": [_r("Paper One", doi="10.1/a", oa_pdf_url="https://x.org/p.pdf")],
    }
    merged = merge_results(by_source)
    assert len(merged) == 1
    assert merged[0].oa_pdf_url == "https://x.org/p.pdf"


def test_merge_fills_missing_abstract_from_later_source():
    by_source = {
        "openalex": [_r("Paper One", doi="10.1/a", abstract=None)],
        "crossref": [_r("Paper One", doi="10.1/a", abstract="An abstract.")],
    }
    merged = merge_results(by_source)
    assert merged[0].abstract == "An abstract."


def test_merge_empty_input_returns_empty_list():
    assert merge_results({}) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_dedup.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'litreview.dedup'`

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/dedup.py`:

```python
from difflib import SequenceMatcher

from .api_clients.base import NormalizedResult


def _normalize_title(t: str) -> str:
    return " ".join(t.lower().split())


def merge_results(
    results_by_source: dict[str, list[NormalizedResult]], threshold: float = 0.85
) -> list[NormalizedResult]:
    merged: list[NormalizedResult] = []
    for results in results_by_source.values():
        for r in results:
            match = None
            for m in merged:
                if r.doi and m.doi and r.doi.lower() == m.doi.lower():
                    match = m
                    break
                similarity = SequenceMatcher(
                    None, _normalize_title(r.title), _normalize_title(m.title)
                ).ratio()
                if similarity >= threshold:
                    match = m
                    break
            if match is None:
                merged.append(r)
            else:
                if not match.oa_pdf_url and r.oa_pdf_url:
                    match.oa_pdf_url = r.oa_pdf_url
                if not match.abstract and r.abstract:
                    match.abstract = r.abstract
    return merged
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_dedup.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/dedup.py backend/tests/test_dedup.py
git commit -m "feat(backend): add search result deduplication"
```

---

### Task 8: PDF download and text extraction

**Files:**
- Create: `backend/src/litreview/pdf_utils.py`
- Test: `backend/tests/test_pdf_utils.py`

**Interfaces:**
- Produces: `pdf_utils.PdfDownloadError`,
  `pdf_utils.download_pdf(url: str, dest: Path) -> Path`,
  `pdf_utils.extract_text(pdf_path: Path, max_pages: int = 30) -> str`,
  `pdf_utils.has_extractable_text(text: str) -> bool`,
  `pdf_utils.MIN_TEXT_CHARS: int`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_pdf_utils.py`:

```python
from unittest.mock import Mock, patch

import pytest
import requests
from fpdf import FPDF
from pypdf import PdfWriter

from litreview import pdf_utils


def _make_text_pdf(tmp_path, text="Hello world. " * 50):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, text)
    path = tmp_path / "text.pdf"
    pdf.output(str(path))
    return path


def _make_blank_pdf(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    path = tmp_path / "blank.pdf"
    with open(path, "wb") as f:
        writer.write(f)
    return path


def test_download_pdf_writes_content(tmp_path):
    mock_resp = Mock()
    mock_resp.content = b"%PDF-1.4 fake content"
    mock_resp.raise_for_status.return_value = None
    dest = tmp_path / "out" / "file.pdf"
    with patch.object(pdf_utils.requests, "get", return_value=mock_resp):
        result = pdf_utils.download_pdf("https://example.org/a.pdf", dest)
    assert result == dest
    assert dest.read_bytes() == b"%PDF-1.4 fake content"


def test_download_pdf_raises_on_request_exception(tmp_path):
    dest = tmp_path / "file.pdf"
    with patch.object(
        pdf_utils.requests, "get", side_effect=requests.RequestException("timeout")
    ):
        with pytest.raises(pdf_utils.PdfDownloadError):
            pdf_utils.download_pdf("https://example.org/a.pdf", dest)


def test_extract_text_returns_pdf_content(tmp_path):
    path = _make_text_pdf(tmp_path)
    text = pdf_utils.extract_text(path)
    assert "Hello world" in text


def test_extract_text_respects_max_pages(tmp_path):
    path = _make_text_pdf(tmp_path)
    text = pdf_utils.extract_text(path, max_pages=0)
    assert text == ""


def test_has_extractable_text_true_for_normal_pdf(tmp_path):
    path = _make_text_pdf(tmp_path)
    text = pdf_utils.extract_text(path)
    assert pdf_utils.has_extractable_text(text) is True


def test_has_extractable_text_false_for_blank_pdf(tmp_path):
    path = _make_blank_pdf(tmp_path)
    text = pdf_utils.extract_text(path)
    assert pdf_utils.has_extractable_text(text) is False


def test_has_extractable_text_false_for_short_text():
    assert pdf_utils.has_extractable_text("too short") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_pdf_utils.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'litreview.pdf_utils'`

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/pdf_utils.py`:

```python
from pathlib import Path

import requests
from pypdf import PdfReader

MIN_TEXT_CHARS = 200


class PdfDownloadError(Exception):
    pass


def download_pdf(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        raise PdfDownloadError(str(e)) from e
    dest.write_bytes(r.content)
    return dest


def extract_text(pdf_path: Path, max_pages: int = 30) -> str:
    reader = PdfReader(str(pdf_path))
    pages = reader.pages[:max_pages]
    return "\n".join(page.extract_text() or "" for page in pages)


def has_extractable_text(text: str) -> bool:
    return len(text.strip()) >= MIN_TEXT_CHARS
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pip install -e ".[dev]"  # picks up fpdf2
.venv/bin/pytest tests/test_pdf_utils.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/pdf_utils.py backend/tests/test_pdf_utils.py
git commit -m "feat(backend): add PDF download and text extraction"
```

---

### Task 9: BibTeX export

**Files:**
- Create: `backend/src/litreview/bib_export.py`
- Test: `backend/tests/test_bib_export.py`

**Interfaces:**
- Produces: `bib_export.make_citekey(authors: list[str], year: int | None, title: str) -> str`,
  `bib_export.to_bibtex(article: dict) -> str`,
  `bib_export.export_bib(articles: list[dict]) -> str`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_bib_export.py`:

```python
from litreview.bib_export import export_bib, make_citekey, to_bibtex


def test_make_citekey_uses_author_year_title():
    key = make_citekey(["Jane Smith"], 2020, "Deep Learning Basics")
    assert key == "Smith2020Deep"


def test_make_citekey_handles_missing_year():
    key = make_citekey(["Jane Smith"], None, "Deep Learning Basics")
    assert key == "SmithndDeep"


def test_make_citekey_handles_empty_authors():
    key = make_citekey([], 2020, "Deep Learning Basics")
    assert key == "Anon2020Deep"


def test_make_citekey_strips_accents_and_punctuation():
    # last whitespace-separated token of authors[0] is "D'Andrea-Bruno";
    # _slug strips the apostrophe and hyphen, and the title's accented
    # first word "Città" normalizes to "Citta".
    key = make_citekey(["Alessandro D'Andrea-Bruno"], 2021, "Città e reti")
    assert key.isascii()
    assert key == "DAndreaBruno2021Citta"


def test_to_bibtex_includes_core_fields():
    article = {
        "bib_key": None,
        "authors": ["Jane Smith", "John Doe"],
        "title": "Deep Learning Basics",
        "year": 2020,
        "doi": "10.1/abc",
    }
    bib = to_bibtex(article)
    assert bib.startswith("@article{Smith2020Deep,")
    assert "author = {Jane Smith and John Doe}" in bib
    assert "title = {Deep Learning Basics}" in bib
    assert "year = {2020}" in bib
    assert "doi = {10.1/abc}" in bib


def test_to_bibtex_uses_explicit_bib_key_if_present():
    article = {
        "bib_key": "custom2020key",
        "authors": ["Jane Smith"],
        "title": "T",
        "year": 2020,
        "doi": None,
    }
    bib = to_bibtex(article)
    assert bib.startswith("@article{custom2020key,")


def test_to_bibtex_omits_empty_optional_fields():
    article = {"bib_key": None, "authors": ["Jane Smith"], "title": "T", "year": None, "doi": None}
    bib = to_bibtex(article)
    assert "doi" not in bib
    assert "year = {}" not in bib


def test_export_bib_joins_multiple_entries():
    articles = [
        {"bib_key": None, "authors": ["A"], "title": "One", "year": 2020, "doi": None},
        {"bib_key": None, "authors": ["B"], "title": "Two", "year": 2021, "doi": None},
    ]
    result = export_bib(articles)
    assert "@article{A2020One" in result
    assert "@article{B2021Two" in result


def test_export_bib_empty_list_returns_empty_string():
    assert export_bib([]) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_bib_export.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'litreview.bib_export'`

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/bib_export.py`:

```python
import re
import unicodedata


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]", "", text)


def make_citekey(authors: list[str], year: int | None, title: str) -> str:
    if authors and authors[0].strip():
        last_word = authors[0].split()[-1]
        author_part = _slug(last_word) or "Anon"
    else:
        author_part = "Anon"
    year_part = str(year) if year else "nd"
    title_words = [w for w in re.split(r"\s+", title) if w]
    title_part = _slug(title_words[0]) if title_words else ""
    return f"{author_part}{year_part}{title_part}"


def to_bibtex(article: dict) -> str:
    key = article.get("bib_key") or make_citekey(
        article["authors"], article.get("year"), article["title"]
    )
    authors = " and ".join(article["authors"])
    year = article.get("year")
    fields = [
        ("author", authors),
        ("title", article["title"]),
        ("year", str(year) if year else ""),
        ("doi", article.get("doi") or ""),
    ]
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields if v)
    return f"@article{{{key},\n{body}\n}}\n"


def export_bib(articles: list[dict]) -> str:
    return "\n".join(to_bibtex(a) for a in articles)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_bib_export.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/bib_export.py backend/tests/test_bib_export.py
git commit -m "feat(backend): add BibTeX citekey generation and export"
```

---

### Task 10: DeepSeek client

**Files:**
- Create: `backend/src/litreview/deepseek_client.py`
- Test: `backend/tests/test_deepseek_client.py`

**Interfaces:**
- Consumes: `config.DEEPSEEK_BASE_URL`, `config.DEEPSEEK_MODEL`
- Produces: `deepseek_client.PROMPTS: dict[str, str]` (keys: `"summary"`,
  `"metadata"`, `"verify"`), `deepseek_client.DeepSeekClient(api_key: str, client=None)`
  with methods `.analyze(mode: str, text: str, *, title="", authors=None, year=None) -> str`
  and `.chat(text: str, messages: list[dict]) -> str`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_deepseek_client.py`:

```python
import pytest

from litreview.deepseek_client import DeepSeekClient


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeCompletion:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, reply="canned reply"):
        self.reply = reply
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return FakeCompletion(self.reply)


class FakeChat:
    def __init__(self, reply="canned reply"):
        self.completions = FakeCompletions(reply)


class FakeOpenAIClient:
    def __init__(self, reply="canned reply"):
        self.chat = FakeChat(reply)


def test_analyze_summary_sends_prompt_and_returns_content():
    fake = FakeOpenAIClient(reply="This is a summary.")
    client = DeepSeekClient(api_key="sk-test", client=fake)
    result = client.analyze("summary", "full article text", title="T", authors=["A"], year=2020)
    assert result == "This is a summary."
    messages = fake.chat.completions.last_kwargs["messages"]
    assert "full article text" in messages[0]["content"]
    assert fake.chat.completions.last_kwargs["model"] == "deepseek-chat"


def test_analyze_metadata_mode_uses_metadata_prompt():
    fake = FakeOpenAIClient(reply="{}")
    client = DeepSeekClient(api_key="sk-test", client=fake)
    client.analyze("metadata", "text")
    content = fake.chat.completions.last_kwargs["messages"][0]["content"]
    assert "JSON" in content


def test_analyze_verify_mode_includes_title_authors_year():
    fake = FakeOpenAIClient(reply="SI")
    client = DeepSeekClient(api_key="sk-test", client=fake)
    client.analyze("verify", "text", title="My Title", authors=["Jane Smith"], year=2019)
    content = fake.chat.completions.last_kwargs["messages"][0]["content"]
    assert "My Title" in content
    assert "Jane Smith" in content
    assert "2019" in content


def test_analyze_unknown_mode_raises_value_error():
    fake = FakeOpenAIClient()
    client = DeepSeekClient(api_key="sk-test", client=fake)
    with pytest.raises(ValueError):
        client.analyze("not_a_mode", "text")


def test_chat_includes_article_text_as_system_message_and_history():
    fake = FakeOpenAIClient(reply="assistant reply")
    client = DeepSeekClient(api_key="sk-test", client=fake)
    history = [{"role": "user", "content": "What is the sample size?"}]
    result = client.chat("article full text", history)
    assert result == "assistant reply"
    sent_messages = fake.chat.completions.last_kwargs["messages"]
    assert sent_messages[0]["role"] == "system"
    assert "article full text" in sent_messages[0]["content"]
    assert sent_messages[1:] == history
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_deepseek_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'litreview.deepseek_client'`

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/deepseek_client.py`:

```python
from openai import OpenAI

from .config import DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

PROMPTS = {
    "summary": (
        "Sei un assistente di ricerca. Riassumi il seguente articolo "
        "scientifico in italiano, in 200-300 parole, evidenziando obiettivo, "
        "metodo e risultati principali.\n\nTesto:\n{text}"
    ),
    "metadata": (
        "Estrai dal seguente testo di articolo scientifico i campi: metodo, "
        "campione, risultati_principali, limiti. Rispondi in formato JSON.\n\n"
        "Testo:\n{text}"
    ),
    "verify": (
        "Confronta i metadati dichiarati (titolo: {title}, autori: {authors}, "
        "anno: {year}) con il contenuto del testo estratto dal PDF seguente. "
        "Indica se corrispondono (SI/NO) e perché.\n\nTesto:\n{text}"
    ),
}


class DeepSeekClient:
    def __init__(self, api_key: str, client: OpenAI | None = None):
        self._client = client or OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)

    def analyze(
        self,
        mode: str,
        text: str,
        *,
        title: str = "",
        authors: list[str] | None = None,
        year: int | None = None,
    ) -> str:
        if mode not in PROMPTS:
            raise ValueError(f"unknown mode: {mode}")
        prompt = PROMPTS[mode].format(
            text=text, title=title, authors=", ".join(authors or []), year=year
        )
        response = self._client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    def chat(self, text: str, messages: list[dict]) -> str:
        system = {
            "role": "system",
            "content": f"Rispondi a domande sul seguente articolo:\n\n{text}",
        }
        response = self._client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[system, *messages],
        )
        return response.choices[0].message.content
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_deepseek_client.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/deepseek_client.py backend/tests/test_deepseek_client.py
git commit -m "feat(backend): add DeepSeek client with 4 analysis modes"
```

---

### Task 11: FastAPI app skeleton + settings router

**Files:**
- Create: `backend/src/litreview/main.py`
- Create: `backend/src/litreview/routers/__init__.py`
- Create: `backend/src/litreview/routers/settings_router.py`
- Modify: `backend/tests/conftest.py` (add `client` fixture)
- Test: `backend/tests/test_settings_router.py`

**Interfaces:**
- Consumes: `keys.KNOWN_KEYS`, `keys.set_key`, `keys.get_key`, `keys.delete_key`,
  `keys.has_key`, `keys.KeyringUnavailableError`, `db.get_db`,
  `api_clients.openalex.search`, `api_clients.semantic_scholar.search`,
  `api_clients.crossref.search`, `api_clients.base.SourceError`,
  `deepseek_client.DeepSeekClient`
- Produces: `main.app` (FastAPI instance), `conftest.client` fixture (TestClient
  with DB dependency override, reusable by later router tasks),
  `POST /settings/keys/{name}/test` → `{"name": str, "ok": bool, "message": str}`
  (spec requires a "Testa connessione" action per key field, consumed by the
  onboarding wizard and Settings screen built in the follow-up desktop-shell plan)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/conftest.py`:

```python


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from litreview import db as db_module
    from litreview.main import app

    test_db_path = tmp_path / "test.db"

    def override_get_db():
        conn = db_module.get_connection(test_db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[db_module.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

`backend/tests/test_settings_router.py`:

```python
from litreview import keys


def test_list_keys_reports_all_known_keys_as_unset(client, monkeypatch):
    monkeypatch.setattr(keys, "has_key", lambda name: False)
    resp = client.get("/settings/keys")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == set(keys.KNOWN_KEYS)
    assert all(v is False for v in data.values())


def test_set_key_calls_keys_set_key(client, monkeypatch):
    calls = {}
    monkeypatch.setattr(keys, "set_key", lambda name, value: calls.setdefault(name, value))
    resp = client.put("/settings/keys/deepseek_api_key", json={"value": "sk-abc"})
    assert resp.status_code == 200
    assert calls["deepseek_api_key"] == "sk-abc"


def test_set_key_unknown_name_returns_404(client):
    resp = client.put("/settings/keys/not_real", json={"value": "x"})
    assert resp.status_code == 404


def test_set_key_keyring_unavailable_returns_503(client, monkeypatch):
    def raise_unavailable(name, value):
        raise keys.KeyringUnavailableError("no backend")

    monkeypatch.setattr(keys, "set_key", raise_unavailable)
    resp = client.put("/settings/keys/deepseek_api_key", json={"value": "sk-abc"})
    assert resp.status_code == 503


def test_delete_key_calls_keys_delete_key(client, monkeypatch):
    calls = []
    monkeypatch.setattr(keys, "delete_key", lambda name: calls.append(name))
    resp = client.delete("/settings/keys/deepseek_api_key")
    assert resp.status_code == 200
    assert calls == ["deepseek_api_key"]


def test_delete_key_unknown_name_returns_404(client):
    resp = client.delete("/settings/keys/not_real")
    assert resp.status_code == 404


def test_test_connection_unknown_key_returns_404(client):
    resp = client.post("/settings/keys/not_real/test", json={"value": "x"})
    assert resp.status_code == 404


def test_test_connection_openalex_success(client, monkeypatch):
    from litreview.api_clients import openalex

    monkeypatch.setattr(openalex, "search", lambda q, mailto=None, per_page=1: [])
    resp = client.post("/settings/keys/openalex_mailto/test", json={"value": "me@example.org"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


def test_test_connection_reports_source_error(client, monkeypatch):
    from litreview.api_clients import openalex
    from litreview.api_clients.base import SourceError

    def raise_error(q, mailto=None, per_page=1):
        raise SourceError("openalex", "bad request")

    monkeypatch.setattr(openalex, "search", raise_error)
    resp = client.post("/settings/keys/openalex_mailto/test", json={"value": "bad"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["message"] == "bad request"


def test_test_connection_semantic_scholar_success(client, monkeypatch):
    from litreview.api_clients import semantic_scholar

    monkeypatch.setattr(semantic_scholar, "search", lambda q, api_key=None, per_page=1: [])
    resp = client.post("/settings/keys/semantic_scholar_key/test", json={"value": "ss-key"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_test_connection_crossref_success(client, monkeypatch):
    from litreview.api_clients import crossref

    monkeypatch.setattr(crossref, "search", lambda q, mailto=None, per_page=1: [])
    resp = client.post("/settings/keys/crossref_mailto/test", json={"value": "me@example.org"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_test_connection_deepseek_success(client, monkeypatch):
    from litreview.routers import settings_router

    class FakeDeepSeek:
        def __init__(self, api_key):
            self.api_key = api_key

        def analyze(self, mode, text, **kwargs):
            return "ok"

    monkeypatch.setattr(settings_router, "DeepSeekClient", FakeDeepSeek)
    resp = client.post("/settings/keys/deepseek_api_key/test", json={"value": "sk-test"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_test_connection_deepseek_reports_failure(client, monkeypatch):
    from litreview.routers import settings_router

    class FailingDeepSeek:
        def __init__(self, api_key):
            pass

        def analyze(self, mode, text, **kwargs):
            raise RuntimeError("invalid api key")

    monkeypatch.setattr(settings_router, "DeepSeekClient", FailingDeepSeek)
    resp = client.post("/settings/keys/deepseek_api_key/test", json={"value": "sk-bad"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "invalid api key" in data["message"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_settings_router.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'litreview.main'`

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/routers/__init__.py`:

```python
```

(empty file)

`backend/src/litreview/routers/settings_router.py`:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import keys
from ..api_clients import crossref, openalex, semantic_scholar
from ..api_clients.base import SourceError
from ..deepseek_client import DeepSeekClient

router = APIRouter(prefix="/settings", tags=["settings"])


class KeyPayload(BaseModel):
    value: str


@router.get("/keys")
def list_keys():
    return {name: keys.has_key(name) for name in keys.KNOWN_KEYS}


@router.put("/keys/{name}")
def set_key(name: str, payload: KeyPayload):
    if name not in keys.KNOWN_KEYS:
        raise HTTPException(status_code=404, detail="unknown key")
    try:
        keys.set_key(name, payload.value)
    except keys.KeyringUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"name": name, "saved": True}


@router.delete("/keys/{name}")
def delete_key(name: str):
    if name not in keys.KNOWN_KEYS:
        raise HTTPException(status_code=404, detail="unknown key")
    keys.delete_key(name)
    return {"name": name, "deleted": True}


def _test_connection(name: str, value: str) -> tuple[bool, str]:
    try:
        if name == "openalex_mailto":
            openalex.search("test", mailto=value, per_page=1)
        elif name == "semantic_scholar_key":
            semantic_scholar.search("test", api_key=value, per_page=1)
        elif name == "crossref_mailto":
            crossref.search("test", mailto=value, per_page=1)
        elif name == "deepseek_api_key":
            DeepSeekClient(value).analyze("summary", "test text for connection check.")
        return True, "ok"
    except SourceError as e:
        return False, e.message
    except Exception as e:
        return False, str(e)


@router.post("/keys/{name}/test")
def test_key(name: str, payload: KeyPayload):
    if name not in keys.KNOWN_KEYS:
        raise HTTPException(status_code=404, detail="unknown key")
    ok, message = _test_connection(name, payload.value)
    return {"name": name, "ok": ok, "message": message}
```

`backend/src/litreview/main.py`:

```python
from fastapi import FastAPI

from .routers import settings_router

app = FastAPI(title="LitReview backend")
app.include_router(settings_router.router)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_settings_router.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/main.py backend/src/litreview/routers/__init__.py \
        backend/src/litreview/routers/settings_router.py \
        backend/tests/conftest.py backend/tests/test_settings_router.py
git commit -m "feat(backend): add FastAPI app skeleton and settings router"
```

---

### Task 12: Search router

**Files:**
- Create: `backend/src/litreview/routers/search_router.py`
- Modify: `backend/src/litreview/main.py` (register router)
- Test: `backend/tests/test_search_router.py`

**Interfaces:**
- Consumes: `keys.get_key`, `api_clients.openalex.search`,
  `api_clients.semantic_scholar.search`, `api_clients.crossref.search`,
  `api_clients.doaj.search`, `api_clients.base.SourceError`,
  `dedup.merge_results`
- Produces: `POST /search` → `{"results": [...], "errors": {source: message}}`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_search_router.py`:

```python
from litreview.api_clients import crossref, doaj, openalex, semantic_scholar
from litreview.api_clients.base import NormalizedResult, SourceError


def test_search_merges_results_from_multiple_sources(client, monkeypatch):
    monkeypatch.setattr(
        openalex,
        "search",
        lambda q, mailto=None, per_page=10: [
            NormalizedResult(
                title="Paper A", authors=["Smith J"], year=2020,
                doi="10.1/a", source="openalex",
            )
        ],
    )
    monkeypatch.setattr(
        semantic_scholar, "search", lambda q, api_key=None, per_page=10: []
    )
    monkeypatch.setattr(crossref, "search", lambda q, mailto=None, per_page=10: [])
    monkeypatch.setattr(doaj, "search", lambda q, per_page=10: [])

    resp = client.post(
        "/search",
        json={"query": "test", "sources": ["openalex", "semantic_scholar", "crossref", "doaj"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["title"] == "Paper A"
    assert data["errors"] == {}


def test_search_reports_per_source_errors_without_failing_whole_request(client, monkeypatch):
    monkeypatch.setattr(openalex, "search", lambda q, mailto=None, per_page=10: [])
    monkeypatch.setattr(
        semantic_scholar,
        "search",
        lambda q, api_key=None, per_page=10: (_ for _ in ()).throw(
            SourceError("semantic_scholar", "timeout")
        ),
    )
    monkeypatch.setattr(crossref, "search", lambda q, mailto=None, per_page=10: [])
    monkeypatch.setattr(doaj, "search", lambda q, per_page=10: [])

    resp = client.post(
        "/search",
        json={"query": "test", "sources": ["openalex", "semantic_scholar", "crossref", "doaj"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"] == []
    assert data["errors"] == {"semantic_scholar": "timeout"}


def test_search_only_queries_requested_sources(client, monkeypatch):
    called = []
    monkeypatch.setattr(
        openalex,
        "search",
        lambda q, mailto=None, per_page=10: called.append("openalex") or [],
    )
    monkeypatch.setattr(
        semantic_scholar,
        "search",
        lambda q, api_key=None, per_page=10: called.append("semantic_scholar") or [],
    )
    resp = client.post("/search", json={"query": "test", "sources": ["openalex"]})
    assert resp.status_code == 200
    assert called == ["openalex"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_search_router.py -v
```

Expected: FAIL — `404 Not Found` (route doesn't exist yet) or import error.

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/routers/search_router.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel

from .. import keys
from ..api_clients import crossref, doaj, openalex, semantic_scholar
from ..api_clients.base import SourceError
from ..dedup import merge_results

router = APIRouter(prefix="/search", tags=["search"])

SOURCE_FUNCS = {
    "openalex": lambda q: openalex.search(q, mailto=keys.get_key("openalex_mailto")),
    "semantic_scholar": lambda q: semantic_scholar.search(
        q, api_key=keys.get_key("semantic_scholar_key")
    ),
    "crossref": lambda q: crossref.search(q, mailto=keys.get_key("crossref_mailto")),
    "doaj": lambda q: doaj.search(q),
}


class SearchRequest(BaseModel):
    query: str
    sources: list[str] = list(SOURCE_FUNCS.keys())


@router.post("")
def search(payload: SearchRequest):
    results_by_source: dict = {}
    errors: dict = {}
    for name in payload.sources:
        fn = SOURCE_FUNCS.get(name)
        if fn is None:
            continue
        try:
            results_by_source[name] = fn(payload.query)
        except SourceError as e:
            errors[name] = e.message
            results_by_source[name] = []

    merged = merge_results(results_by_source)
    return {
        "results": [r.__dict__ for r in merged],
        "errors": errors,
    }
```

Modify `backend/src/litreview/main.py`:

```python
from fastapi import FastAPI

from .routers import search_router, settings_router

app = FastAPI(title="LitReview backend")
app.include_router(settings_router.router)
app.include_router(search_router.router)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_search_router.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/routers/search_router.py backend/src/litreview/main.py \
        backend/tests/test_search_router.py
git commit -m "feat(backend): add multi-source search endpoint with dedup and error reporting"
```

---

### Task 13: Library router (CRUD, download, upload)

**Files:**
- Create: `backend/src/litreview/routers/library_router.py`
- Modify: `backend/src/litreview/main.py` (register router)
- Test: `backend/tests/test_library_router.py`

**Interfaces:**
- Consumes: `db.get_db`, `config.PDF_DIR`, `pdf_utils.download_pdf`,
  `pdf_utils.extract_text`, `pdf_utils.has_extractable_text`,
  `pdf_utils.PdfDownloadError`
- Produces: `POST /library`, `GET /library`, `GET /library/{id}`,
  `POST /library/{id}/download`, `POST /library/{id}/upload`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_library_router.py`:

```python
import io

from litreview import pdf_utils
from litreview.routers import library_router


def _add_sample_article(client, oa_pdf_url=None):
    resp = client.post(
        "/library",
        json={
            "title": "Paper One",
            "authors": ["Jane Smith"],
            "year": 2020,
            "doi": "10.1/a",
            "source": "openalex",
            "abstract": "An abstract.",
            "oa_pdf_url": oa_pdf_url,
        },
    )
    assert resp.status_code == 200
    return resp.json()


def test_add_and_list_article(client):
    created = _add_sample_article(client)
    assert created["title"] == "Paper One"
    assert created["authors"] == ["Jane Smith"]

    resp = client.get("/library")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_article_by_id(client):
    created = _add_sample_article(client)
    resp = client.get(f"/library/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_missing_article_returns_404(client):
    resp = client.get("/library/999")
    assert resp.status_code == 404


def test_download_pdf_without_oa_url_returns_400(client):
    created = _add_sample_article(client, oa_pdf_url=None)
    resp = client.post(f"/library/{created['id']}/download")
    assert resp.status_code == 400


def test_download_pdf_success_updates_article(client, monkeypatch, tmp_path):
    monkeypatch.setattr(library_router, "PDF_DIR", tmp_path)
    monkeypatch.setattr(
        pdf_utils, "download_pdf", lambda url, dest: dest.write_bytes(b"x") or dest
    )
    monkeypatch.setattr(pdf_utils, "extract_text", lambda path, max_pages=30: "a" * 300)
    monkeypatch.setattr(pdf_utils, "has_extractable_text", lambda text: True)

    created = _add_sample_article(client, oa_pdf_url="https://example.org/a.pdf")
    resp = client.post(f"/library/{created['id']}/download")
    assert resp.status_code == 200
    data = resp.json()
    assert data["extracted_text_ok"] is True
    assert data["pdf_path"] is not None


def test_download_pdf_failure_returns_502(client, monkeypatch):
    def raise_download_error(url, dest):
        raise pdf_utils.PdfDownloadError("network error")

    monkeypatch.setattr(pdf_utils, "download_pdf", raise_download_error)
    created = _add_sample_article(client, oa_pdf_url="https://example.org/a.pdf")
    resp = client.post(f"/library/{created['id']}/download")
    assert resp.status_code == 502


def test_upload_pdf_updates_article(client, monkeypatch, tmp_path):
    monkeypatch.setattr(library_router, "PDF_DIR", tmp_path)
    monkeypatch.setattr(pdf_utils, "extract_text", lambda path, max_pages=30: "a" * 300)
    monkeypatch.setattr(pdf_utils, "has_extractable_text", lambda text: True)

    created = _add_sample_article(client)
    resp = client.post(
        f"/library/{created['id']}/upload",
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 content"), "application/pdf")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["extracted_text_ok"] is True


def test_upload_pdf_missing_article_returns_404(client, tmp_path):
    resp = client.post(
        "/library/999/upload",
        files={"file": ("test.pdf", io.BytesIO(b"x"), "application/pdf")},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_library_router.py -v
```

Expected: FAIL — module/route not found.

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/routers/library_router.py`:

```python
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from .. import db as db_module
from .. import pdf_utils
from ..config import PDF_DIR

router = APIRouter(prefix="/library", tags=["library"])


class ArticleIn(BaseModel):
    title: str
    authors: list[str]
    year: int | None = None
    doi: str | None = None
    source: str
    abstract: str | None = None
    oa_pdf_url: str | None = None


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["authors"] = json.loads(d["authors"])
    d["extracted_text_ok"] = bool(d["extracted_text_ok"])
    return d


@router.post("")
def add_article(article: ArticleIn, conn=Depends(db_module.get_db)):
    cur = conn.execute(
        "INSERT INTO articles (title, authors, year, doi, source, abstract, "
        "oa_pdf_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            article.title,
            json.dumps(article.authors),
            article.year,
            article.doi,
            article.source,
            article.abstract,
            article.oa_pdf_url,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_dict(row)


@router.get("")
def list_articles(conn=Depends(db_module.get_db)):
    rows = conn.execute("SELECT * FROM articles ORDER BY created_at DESC").fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/{article_id}")
def get_article(article_id: int, conn=Depends(db_module.get_db)):
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="article not found")
    return _row_to_dict(row)


@router.post("/{article_id}/download")
def download_pdf(article_id: int, conn=Depends(db_module.get_db)):
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="article not found")
    if not row["oa_pdf_url"]:
        raise HTTPException(status_code=400, detail="no open access PDF url available")

    dest = PDF_DIR / f"{article_id}.pdf"
    try:
        pdf_utils.download_pdf(row["oa_pdf_url"], dest)
    except pdf_utils.PdfDownloadError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    text = pdf_utils.extract_text(dest)
    ok = pdf_utils.has_extractable_text(text)
    conn.execute(
        "UPDATE articles SET pdf_path = ?, extracted_text_ok = ? WHERE id = ?",
        (str(dest), int(ok), article_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    return _row_to_dict(row)


@router.post("/{article_id}/upload")
async def upload_pdf(article_id: int, file: UploadFile, conn=Depends(db_module.get_db)):
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="article not found")

    dest = PDF_DIR / f"{article_id}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    dest.write_bytes(content)

    text = pdf_utils.extract_text(dest)
    ok = pdf_utils.has_extractable_text(text)
    conn.execute(
        "UPDATE articles SET pdf_path = ?, extracted_text_ok = ? WHERE id = ?",
        (str(dest), int(ok), article_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    return _row_to_dict(row)
```

Modify `backend/src/litreview/main.py`:

```python
from fastapi import FastAPI

from .routers import library_router, search_router, settings_router

app = FastAPI(title="LitReview backend")
app.include_router(settings_router.router)
app.include_router(search_router.router)
app.include_router(library_router.router)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_library_router.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/routers/library_router.py backend/src/litreview/main.py \
        backend/tests/test_library_router.py
git commit -m "feat(backend): add library CRUD, PDF download, and PDF upload endpoints"
```

---

### Task 14: Analysis router (DeepSeek analyze + chat)

**Files:**
- Create: `backend/src/litreview/routers/analysis_router.py`
- Modify: `backend/src/litreview/main.py` (register router)
- Test: `backend/tests/test_analysis_router.py`

**Interfaces:**
- Consumes: `db.get_db`, `keys.get_key`, `deepseek_client.DeepSeekClient`,
  `pdf_utils.extract_text`
- Produces: `POST /library/{id}/analyze`, `POST /library/{id}/chat`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_analysis_router.py`:

```python
import json

from litreview import keys, pdf_utils
from litreview.routers import analysis_router


class FakeDeepSeekClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def analyze(self, mode, text, *, title="", authors=None, year=None):
        return f"analysis:{mode}"

    def chat(self, text, messages):
        return "assistant reply"


def _add_article_with_pdf(client, conn_monkeypatch=None):
    resp = client.post(
        "/library",
        json={
            "title": "Paper One", "authors": ["Jane Smith"], "year": 2020,
            "doi": "10.1/a", "source": "openalex", "abstract": "abs",
            "oa_pdf_url": "https://example.org/a.pdf",
        },
    )
    article = resp.json()
    return article


def test_analyze_without_key_returns_400(client, monkeypatch):
    monkeypatch.setattr(keys, "get_key", lambda name: None)
    article = _add_article_with_pdf(client)
    resp = client.post(f"/library/{article['id']}/analyze", json={"mode": "summary"})
    assert resp.status_code == 400


def test_analyze_without_pdf_returns_400(client, monkeypatch):
    monkeypatch.setattr(keys, "get_key", lambda name: "sk-test")
    article = _add_article_with_pdf(client)
    resp = client.post(f"/library/{article['id']}/analyze", json={"mode": "summary"})
    assert resp.status_code == 400


def test_analyze_success_stores_and_returns_result(client, monkeypatch, tmp_path):
    monkeypatch.setattr(keys, "get_key", lambda name: "sk-test")
    monkeypatch.setattr(analysis_router, "DeepSeekClient", FakeDeepSeekClient)
    monkeypatch.setattr(pdf_utils, "extract_text", lambda path, max_pages=30: "full text")

    article = _add_article_with_pdf(client)
    # simulate a completed download by writing directly through the library router's DB
    from litreview.routers import library_router
    monkeypatch.setattr(library_router, "PDF_DIR", tmp_path)
    monkeypatch.setattr(
        pdf_utils, "download_pdf", lambda url, dest: dest.write_bytes(b"x") or dest
    )
    monkeypatch.setattr(pdf_utils, "has_extractable_text", lambda text: True)
    client.post(f"/library/{article['id']}/download")

    resp = client.post(f"/library/{article['id']}/analyze", json={"mode": "summary"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] == "analysis:summary"

    stored = client.get(f"/library/{article['id']}").json()
    assert json.loads(stored["analysis_json"])["summary"] == "analysis:summary"


def test_analyze_unmapped_article_returns_404(client, monkeypatch):
    monkeypatch.setattr(keys, "get_key", lambda name: "sk-test")
    resp = client.post("/library/999/analyze", json={"mode": "summary"})
    assert resp.status_code == 404


def test_chat_creates_session_and_returns_reply(client, monkeypatch, tmp_path):
    monkeypatch.setattr(keys, "get_key", lambda name: "sk-test")
    monkeypatch.setattr(analysis_router, "DeepSeekClient", FakeDeepSeekClient)
    monkeypatch.setattr(pdf_utils, "extract_text", lambda path, max_pages=30: "full text")

    from litreview.routers import library_router
    monkeypatch.setattr(library_router, "PDF_DIR", tmp_path)
    monkeypatch.setattr(
        pdf_utils, "download_pdf", lambda url, dest: dest.write_bytes(b"x") or dest
    )
    monkeypatch.setattr(pdf_utils, "has_extractable_text", lambda text: True)

    article = _add_article_with_pdf(client)
    client.post(f"/library/{article['id']}/download")

    resp = client.post(f"/library/{article['id']}/chat", json={"message": "What is the sample?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "assistant reply"
    assert len(data["messages"]) == 2


def test_chat_without_pdf_returns_400(client, monkeypatch):
    monkeypatch.setattr(keys, "get_key", lambda name: "sk-test")
    article = _add_article_with_pdf(client)
    resp = client.post(f"/library/{article['id']}/chat", json={"message": "hi"})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_analysis_router.py -v
```

Expected: FAIL — module/route not found.

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/routers/analysis_router.py`:

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db as db_module
from .. import keys
from .. import pdf_utils
from ..deepseek_client import DeepSeekClient

router = APIRouter(prefix="/library", tags=["analysis"])


class AnalyzeRequest(BaseModel):
    mode: str


class ChatRequest(BaseModel):
    message: str


def _get_client() -> DeepSeekClient:
    api_key = keys.get_key("deepseek_api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="DeepSeek API key not configured")
    return DeepSeekClient(api_key)


def _require_article_with_text(article_id: int, conn):
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="article not found")
    if not row["pdf_path"] or not row["extracted_text_ok"]:
        raise HTTPException(status_code=400, detail="no extractable PDF text for this article")
    return row


@router.post("/{article_id}/analyze")
def analyze(article_id: int, payload: AnalyzeRequest, conn=Depends(db_module.get_db)):
    client = _get_client()
    row = _require_article_with_text(article_id, conn)
    text = pdf_utils.extract_text(Path(row["pdf_path"]))
    authors = json.loads(row["authors"])
    result = client.analyze(payload.mode, text, title=row["title"], authors=authors, year=row["year"])

    analysis = json.loads(row["analysis_json"]) if row["analysis_json"] else {}
    analysis[payload.mode] = result
    conn.execute(
        "UPDATE articles SET analysis_json = ? WHERE id = ?", (json.dumps(analysis), article_id)
    )
    conn.commit()
    return {"article_id": article_id, "mode": payload.mode, "result": result}


@router.post("/{article_id}/chat")
def chat(article_id: int, payload: ChatRequest, conn=Depends(db_module.get_db)):
    client = _get_client()
    row = _require_article_with_text(article_id, conn)
    text = pdf_utils.extract_text(Path(row["pdf_path"]))

    session = conn.execute(
        "SELECT * FROM chat_sessions WHERE article_id = ? ORDER BY id DESC LIMIT 1",
        (article_id,),
    ).fetchone()
    messages = json.loads(session["messages_json"]) if session else []
    messages.append({"role": "user", "content": payload.message})

    reply = client.chat(text, messages)
    messages.append({"role": "assistant", "content": reply})

    now = datetime.now(timezone.utc).isoformat()
    if session:
        conn.execute(
            "UPDATE chat_sessions SET messages_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(messages), now, session["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO chat_sessions (article_id, messages_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (article_id, json.dumps(messages), now, now),
        )
    conn.commit()
    return {"article_id": article_id, "reply": reply, "messages": messages}
```

Modify `backend/src/litreview/main.py`:

```python
from fastapi import FastAPI

from .routers import analysis_router, library_router, search_router, settings_router

app = FastAPI(title="LitReview backend")
app.include_router(settings_router.router)
app.include_router(search_router.router)
app.include_router(library_router.router)
app.include_router(analysis_router.router)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_analysis_router.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/routers/analysis_router.py backend/src/litreview/main.py \
        backend/tests/test_analysis_router.py
git commit -m "feat(backend): add DeepSeek analyze and chat endpoints"
```

---

### Task 15: Export router

**Files:**
- Create: `backend/src/litreview/routers/export_router.py`
- Modify: `backend/src/litreview/main.py` (register router)
- Test: `backend/tests/test_export_router.py`

**Interfaces:**
- Consumes: `db.get_db`, `bib_export.export_bib`
- Produces: `POST /export/bib`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_export_router.py`:

```python
def _add_article(client, title, authors, year=2020, doi=None):
    resp = client.post(
        "/library",
        json={
            "title": title, "authors": authors, "year": year, "doi": doi,
            "source": "openalex", "abstract": None, "oa_pdf_url": None,
        },
    )
    return resp.json()


def test_export_bib_returns_bibtex_for_selected_articles(client):
    a1 = _add_article(client, "Paper One", ["Jane Smith"])
    _add_article(client, "Paper Two", ["John Doe"])  # not selected

    resp = client.post("/export/bib", json={"article_ids": [a1["id"]]})
    assert resp.status_code == 200
    bib = resp.json()["bib"]
    assert "@article{Smith2020Paper" in bib
    assert "Paper Two" not in bib


def test_export_bib_skips_missing_ids(client):
    a1 = _add_article(client, "Paper One", ["Jane Smith"])
    resp = client.post("/export/bib", json={"article_ids": [a1["id"], 999]})
    assert resp.status_code == 200
    assert resp.json()["bib"].count("@article") == 1


def test_export_bib_empty_selection_returns_empty_string(client):
    resp = client.post("/export/bib", json={"article_ids": []})
    assert resp.status_code == 200
    assert resp.json()["bib"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_export_router.py -v
```

Expected: FAIL — module/route not found.

- [ ] **Step 3: Write the implementation**

`backend/src/litreview/routers/export_router.py`:

```python
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import db as db_module
from ..bib_export import export_bib

router = APIRouter(prefix="/export", tags=["export"])


class ExportRequest(BaseModel):
    article_ids: list[int]


@router.post("/bib")
def export(payload: ExportRequest, conn=Depends(db_module.get_db)):
    articles = []
    for aid in payload.article_ids:
        row = conn.execute("SELECT * FROM articles WHERE id = ?", (aid,)).fetchone()
        if row is None:
            continue
        d = dict(row)
        d["authors"] = json.loads(d["authors"])
        articles.append(d)
    return {"bib": export_bib(articles)}
```

Modify `backend/src/litreview/main.py`:

```python
from fastapi import FastAPI

from .routers import analysis_router, export_router, library_router, search_router, settings_router

app = FastAPI(title="LitReview backend")
app.include_router(settings_router.router)
app.include_router(search_router.router)
app.include_router(library_router.router)
app.include_router(analysis_router.router)
app.include_router(export_router.router)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_export_router.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/litreview/routers/export_router.py backend/src/litreview/main.py \
        backend/tests/test_export_router.py
git commit -m "feat(backend): add .bib export endpoint"
```

---

### Task 16: CORS wiring, integration smoke test, backend README

**Files:**
- Modify: `backend/src/litreview/main.py` (add CORS middleware)
- Test: `backend/tests/test_integration_smoke.py`
- Create: `backend/README.md`

**Interfaces:**
- Consumes: everything produced by Tasks 1–15
- Produces: nothing new — this task wires and documents the finished service

- [ ] **Step 1: Write the failing integration test**

`backend/tests/test_integration_smoke.py`:

```python
from litreview import keys, pdf_utils
from litreview.routers import analysis_router, library_router


class FakeDeepSeekClient:
    def __init__(self, api_key):
        pass

    def analyze(self, mode, text, *, title="", authors=None, year=None):
        return f"analysis:{mode}"

    def chat(self, text, messages):
        return "assistant reply"


def test_full_flow_add_download_analyze_export(client, monkeypatch, tmp_path):
    monkeypatch.setattr(library_router, "PDF_DIR", tmp_path)
    monkeypatch.setattr(
        pdf_utils, "download_pdf", lambda url, dest: dest.write_bytes(b"x") or dest
    )
    monkeypatch.setattr(pdf_utils, "extract_text", lambda path, max_pages=30: "a" * 300)
    monkeypatch.setattr(pdf_utils, "has_extractable_text", lambda text: True)
    monkeypatch.setattr(keys, "get_key", lambda name: "sk-test")
    monkeypatch.setattr(analysis_router, "DeepSeekClient", FakeDeepSeekClient)

    created = client.post(
        "/library",
        json={
            "title": "Integration Paper", "authors": ["Ada Lovelace"], "year": 2022,
            "doi": "10.9/int", "source": "openalex", "abstract": "abs",
            "oa_pdf_url": "https://example.org/int.pdf",
        },
    ).json()

    downloaded = client.post(f"/library/{created['id']}/download").json()
    assert downloaded["extracted_text_ok"] is True

    analyzed = client.post(f"/library/{created['id']}/analyze", json={"mode": "summary"}).json()
    assert analyzed["result"] == "analysis:summary"

    exported = client.post("/export/bib", json={"article_ids": [created["id"]]}).json()
    assert "@article{Lovelace2022Integration" in exported["bib"]


def test_cors_headers_present_for_local_origin(client):
    resp = client.options(
        "/library",
        headers={
            "Origin": "http://localhost:1420",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") in ("http://localhost:1420", "*")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_integration_smoke.py -v
```

Expected: the CORS test FAILs (no `access-control-allow-origin` header yet); the
full-flow test should already pass from prior tasks — if so, that's expected,
only the CORS assertion is new behavior under test.

- [ ] **Step 3: Add CORS middleware**

Modify `backend/src/litreview/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import analysis_router, export_router, library_router, search_router, settings_router

app = FastAPI(title="LitReview backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings_router.router)
app.include_router(search_router.router)
app.include_router(library_router.router)
app.include_router(analysis_router.router)
app.include_router(export_router.router)
```

(`allow_origins=["*"]` is acceptable here: the server binds to `127.0.0.1`
only and is never exposed beyond the local machine — see README.)

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest -v
```

Expected: all tests in the suite PASS.

- [ ] **Step 5: Write the backend README**

`backend/README.md`:

```markdown
# LitReview backend

Servizio FastAPI locale: ricerca multi-fonte (OpenAlex, Semantic Scholar,
Crossref, DOAJ), download/upload PDF, analisi DeepSeek, libreria SQLite,
export `.bib`.

## Setup

\`\`\`bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
\`\`\`

## Test

\`\`\`bash
.venv/bin/pytest -v
\`\`\`

## Avvio locale

\`\`\`bash
.venv/bin/uvicorn litreview.main:app --host 127.0.0.1 --port 8756 --reload
\`\`\`

Il servizio ascolta solo su `127.0.0.1`: non è mai esposto oltre la macchina
locale. Le chiavi API si configurano via `PUT /settings/keys/{name}` e sono
salvate nel keyring di sistema, mai in chiaro su disco.

## Note per l'integrazione futura (shell desktop Tauri)

Questo backend è pensato per essere lanciato come sidecar da un'app Tauri
(vedi `docs/superpowers/specs/2026-08-17-literature-review-app-design.md`).
Sarà compilato con PyInstaller in un binario standalone e incluso nel bundle
Tauri tramite `externalBin`. Questa parte è coperta da un piano separato.
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/litreview/main.py backend/tests/test_integration_smoke.py backend/README.md
git commit -m "feat(backend): wire CORS, add integration smoke test and README"
```

---

## Definition of Done

- `cd backend && .venv/bin/pytest -v` passes with 0 failures.
- `uvicorn litreview.main:app --host 127.0.0.1 --port 8756` starts without
  error and `GET /settings/keys` (via curl/httpx) returns all 4 known keys
  as `false`.
- No plaintext API key ever touches disk (verified by `keys.py` tests using
  a fake in-memory keyring backend, never the filesystem).
- Every commit corresponds to exactly one task above.
