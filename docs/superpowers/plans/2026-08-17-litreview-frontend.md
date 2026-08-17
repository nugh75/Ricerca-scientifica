# LitReview Frontend (Tauri) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a compact, one-click desktop app (`frontend/`) that wraps the existing LitReview backend as a Tauri sidecar and gives non-technical users a GUI for search, library, PDF analysis/chat, and `.bib` export.

**Architecture:** Tauri 2 shell (Rust) spawns the already-built PyInstaller backend binary as an `externalBin` sidecar on startup and kills it on exit. A vanilla TypeScript + Vite frontend talks to the sidecar over `http://127.0.0.1:8756` (fixed host/port, see `backend/src/litreview/__main__.py`). No new backend code is written or modified by this plan — it is 100% additive, consuming the backend's existing REST API as-is.

**Tech Stack:** Tauri 2 (Rust, `tauri-plugin-shell`, `tauri-plugin-dialog`), Vite + TypeScript (vanilla, no UI framework), Vitest + jsdom for unit tests.

**Spec:** `docs/superpowers/specs/2026-08-17-literature-review-app-design.md`

## Global Constraints

- Backend base URL is fixed: `http://127.0.0.1:8756` (not dynamic — the spec's "porta scelta dinamicamente" language predates the shipped backend, which hardcodes host/port in `backend/src/litreview/__main__.py`; this plan follows the shipped backend, not the older spec wording).
- No backend code changes. All frontend work reads the API as implemented in `backend/src/litreview/routers/*.py`.
- macOS backend binary is Apple Silicon (arm64) only (existing constraint, see `backend/README.md`) — the desktop app's macOS build targets `aarch64-apple-darwin` only, no Intel/universal build.
- `first_run_done` (onboarding gate) is **not** a backend concept — the backend's `settings` SQLite table exists but no router exposes it. This plan stores the onboarding-complete flag in the webview's `localStorage`, not via a backend call. Do not add a backend endpoint for this (YAGNI — it's a pure UI concern).
- Frontend test policy follows the spec: automated unit tests cover logic-bearing modules (API client, router, first-run gate, small pure helpers). Screen rendering/wiring is verified manually per the spec's "test manuale dei flussi critici, nessun E2E automatizzato in v1" — do not invent E2E/browser automation tests that weren't asked for.
- This plan's executor (agent or human) does not have a GUI/display available in the sandbox that authored this plan. `cargo build`, `npm run build`, and `vitest run` are all runnable headlessly and must actually be run and pass at each step. `npm run tauri dev` (the real app window) cannot be verified headlessly — flag it for manual verification by the user instead of claiming it works.

---

## File Structure

```
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── vitest.config.ts
├── index.html
├── scripts/
│   └── prepare-sidecar.mjs        # copies backend/dist/* into src-tauri/binaries/ with target-triple names
├── src/
│   ├── main.ts                     # entry point: mounts nav + router + backend-readiness gate
│   ├── style.css
│   ├── api.ts                       # typed fetch wrappers for every backend endpoint
│   ├── router.ts                     # tiny hash router
│   ├── firstRun.ts                    # onboarding-complete flag (localStorage)
│   ├── keysState.ts                    # caches GET /settings/keys, notifies subscribers
│   ├── views/
│   │   ├── onboarding.ts
│   │   ├── settings.ts
│   │   ├── keyField.ts                  # shared key-row widget used by settings + onboarding
│   │   ├── search.ts
│   │   ├── library.ts
│   │   ├── articleDetail.ts              # metadata + analysis + chat panel
│   │   └── export.ts
│   └── helpers.ts                     # small pure functions used by views (tested)
├── tests/
│   ├── api.test.ts
│   ├── router.test.ts
│   ├── firstRun.test.ts
│   └── helpers.test.ts
└── src-tauri/
    ├── Cargo.toml
    ├── build.rs
    ├── tauri.conf.json
    ├── capabilities/
    │   └── default.json
    ├── binaries/                    # gitignored, populated by prepare-sidecar.mjs
    └── src/
        └── main.rs                    # sidecar lifecycle + write_export command
```

---

### Task 1: Scaffold the Tauri + Vite project

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/vitest.config.ts`, `frontend/index.html`, `frontend/src/main.ts`, `frontend/src/style.css`
- Create: `frontend/src-tauri/Cargo.toml`, `frontend/src-tauri/build.rs`, `frontend/src-tauri/tauri.conf.json`, `frontend/src-tauri/capabilities/default.json`, `frontend/src-tauri/src/main.rs`
- Create: `frontend/.gitignore`

**Interfaces:**
- Produces: a `npm run build` (Vite → `frontend/dist/`) and `cargo build` (in `frontend/src-tauri/`) that both succeed. Every later task builds on this skeleton.

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "litreview-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -p tsconfig.json --noEmit && vite build",
    "test": "vitest run",
    "tauri": "tauri"
  },
  "dependencies": {
    "@tauri-apps/api": "^2.1.1",
    "@tauri-apps/plugin-dialog": "^2.0.1"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^2.1.0",
    "typescript": "^5.6.3",
    "vite": "^5.4.9",
    "vitest": "^2.1.3",
    "jsdom": "^25.0.1"
  }
}
```

- [ ] **Step 2: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "lib": ["ES2022", "DOM"],
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "skipLibCheck": true,
    "esModuleInterop": true
  },
  "include": ["src", "tests"]
}
```

- [ ] **Step 3: Create `frontend/vite.config.ts`**

```ts
import { defineConfig } from "vite";

export default defineConfig({
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
  },
});
```

- [ ] **Step 4: Create `frontend/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts"],
  },
});
```

- [ ] **Step 5: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="it">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>LitReview</title>
    <link rel="stylesheet" href="/src/style.css" />
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 6: Create `frontend/src/style.css`**

```css
:root {
  color-scheme: light dark;
  font-family: system-ui, sans-serif;
}
body { margin: 0; }
#app { display: flex; flex-direction: column; min-height: 100vh; }
nav { display: flex; gap: 1rem; padding: 0.75rem 1rem; border-bottom: 1px solid #8884; }
nav a { text-decoration: none; cursor: pointer; }
main { flex: 1; padding: 1rem; }
.banner { padding: 0.5rem 1rem; }
.banner-error { background: #c0392b; color: white; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid #8884; padding: 0.4rem; text-align: left; }
.badge { display: inline-block; padding: 0.1rem 0.4rem; border-radius: 0.3rem; font-size: 0.8rem; }
.badge-ok { background: #2ecc71; color: white; }
.badge-warn { background: #e67e22; color: white; }
.badge-error { background: #c0392b; color: white; }
```

- [ ] **Step 7: Create placeholder `frontend/src/main.ts`** (real content lands in Task 3; for now just enough to make the build succeed)

```ts
document.querySelector<HTMLDivElement>("#app")!.innerHTML = "<p>LitReview</p>";
```

- [ ] **Step 8: Create `frontend/.gitignore`**

```
node_modules/
dist/
src-tauri/target/
src-tauri/binaries/
src-tauri/gen/
```

- [ ] **Step 9: Install frontend deps and verify the web build**

Run: `cd frontend && npm install && npm run build`
Expected: exits 0, produces `frontend/dist/index.html`.

- [ ] **Step 10: Create `frontend/src-tauri/Cargo.toml`**

```toml
[package]
name = "litreview"
version = "0.1.0"
edition = "2021"

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2", features = [] }
tauri-plugin-shell = "2"
tauri-plugin-dialog = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"

[[bin]]
name = "litreview"
path = "src/main.rs"
```

- [ ] **Step 11: Create `frontend/src-tauri/build.rs`**

```rust
fn main() {
    tauri_build::build()
}
```

- [ ] **Step 12: Create `frontend/src-tauri/tauri.conf.json`**

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "LitReview",
  "version": "0.1.0",
  "identifier": "org.litreview.app",
  "build": {
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build",
    "devUrl": "http://localhost:1420",
    "frontendDist": "../dist"
  },
  "app": {
    "windows": [
      {
        "title": "LitReview",
        "width": 1100,
        "height": 760,
        "minWidth": 800,
        "minHeight": 600
      }
    ],
    "security": {
      "csp": null
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ],
    "externalBin": ["binaries/litreview-backend"]
  }
}
```

- [ ] **Step 13: Create `frontend/src-tauri/capabilities/default.json`**

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "description": "Capability for the main window",
  "windows": ["main"],
  "permissions": [
    "core:default",
    {
      "identifier": "shell:allow-execute",
      "allow": [{ "name": "binaries/litreview-backend", "sidecar": true }]
    },
    "dialog:allow-save"
  ]
}
```

- [ ] **Step 14: Create a placeholder icon and generate the icon set**

Tauri's bundler refuses to build without the icon files referenced in `tauri.conf.json`. Generate them from one placeholder square PNG using the Tauri CLI's icon generator (requires ImageMagick's `convert`; install with `sudo apt-get install -y imagemagick` if missing).

Run:
```bash
cd frontend
convert -size 1024x1024 xc:'#2b6cb0' src-tauri/icon-source.png
npx tauri icon src-tauri/icon-source.png
rm src-tauri/icon-source.png
```
Expected: `frontend/src-tauri/icons/` now contains `32x32.png`, `128x128.png`, `128x128@2x.png`, `icon.icns`, `icon.ico` (and a few more sizes, which is fine).

- [ ] **Step 15: Create `frontend/src-tauri/src/main.rs`** (placeholder; real sidecar logic lands in Task 4)

```rust
fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 16: Install Rust toolchain if missing, then verify the Rust build**

If `cargo` is not on PATH, install it:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
```

Run: `cd frontend/src-tauri && cargo build`
Expected: exits 0. This does not require a display — `cargo build` only compiles, it doesn't launch a window.

- [ ] **Step 17: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Tauri + Vite project skeleton"
```

---

### Task 2: Typed API client

**Files:**
- Create: `frontend/src/api.ts`
- Test: `frontend/tests/api.test.ts`

**Interfaces:**
- Consumes: nothing (talks directly to the backend REST API described below).
- Produces: `export const BASE_URL = "http://127.0.0.1:8756"` and the functions every later view imports:
  - `searchArticles(query: string, sources: string[]): Promise<SearchResponse>`
  - `listArticles(): Promise<Article[]>`
  - `getArticle(id: number): Promise<Article>`
  - `addArticle(article: ArticleIn): Promise<Article>`
  - `downloadPdf(id: number): Promise<Article>`
  - `uploadPdf(id: number, file: File): Promise<Article>`
  - `analyze(id: number, mode: "summary" | "metadata" | "verify"): Promise<AnalyzeResponse>`
  - `sendChatMessage(id: number, message: string): Promise<ChatResponse>`
  - `exportBib(articleIds: number[]): Promise<string>`
  - `listKeys(): Promise<Record<string, boolean>>`
  - `setKey(name: string, value: string): Promise<void>`
  - `deleteKey(name: string): Promise<void>`
  - `testKey(name: string, value: string): Promise<{ ok: boolean; message: string }>`
  - `KNOWN_KEYS: readonly string[]` = `["openalex_mailto", "semantic_scholar_key", "crossref_mailto", "deepseek_api_key"]`
  - `SOURCES: readonly string[]` = `["openalex", "semantic_scholar", "crossref", "doaj"]`
  - All functions throw `ApiError` (a small class with `status` and `detail`) on a non-2xx response, reading the FastAPI `{"detail": "..."}` body when present.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/tests/api.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { BASE_URL, ApiError, searchArticles, listArticles, addArticle, analyze, exportBib, setKey, testKey } from "../src/api";

function mockFetchOnce(body: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("posts a search request with query and sources", async () => {
    const fetchMock = mockFetchOnce({ results: [], errors: {} });
    await searchArticles("deep learning", ["openalex", "doaj"]);
    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/search`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ query: "deep learning", sources: ["openalex", "doaj"] }),
      })
    );
  });

  it("lists articles via GET /library", async () => {
    const fetchMock = mockFetchOnce([{ id: 1, title: "A" }]);
    const result = await listArticles();
    expect(fetchMock).toHaveBeenCalledWith(`${BASE_URL}/library`, expect.objectContaining({ method: "GET" }));
    expect(result).toEqual([{ id: 1, title: "A" }]);
  });

  it("adds an article via POST /library", async () => {
    const fetchMock = mockFetchOnce({ id: 1 });
    await addArticle({ title: "T", authors: ["A"], source: "openalex" });
    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/library`,
      expect.objectContaining({ method: "POST" })
    );
  });

  it("calls analyze with the mode in the body", async () => {
    const fetchMock = mockFetchOnce({ article_id: 1, mode: "summary", result: "ok" });
    await analyze(1, "summary");
    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/library/1/analyze`,
      expect.objectContaining({ method: "POST", body: JSON.stringify({ mode: "summary" }) })
    );
  });

  it("returns the bib string from export", async () => {
    mockFetchOnce({ bib: "@article{...}" });
    const bib = await exportBib([1, 2]);
    expect(bib).toBe("@article{...}");
  });

  it("PUTs a key value", async () => {
    const fetchMock = mockFetchOnce({ name: "deepseek_api_key", saved: true });
    await setKey("deepseek_api_key", "sk-test");
    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/settings/keys/deepseek_api_key`,
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ value: "sk-test" }) })
    );
  });

  it("tests a key and returns ok/message", async () => {
    mockFetchOnce({ name: "deepseek_api_key", ok: false, message: "invalid key" });
    const result = await testKey("deepseek_api_key", "bad");
    expect(result).toEqual({ ok: false, message: "invalid key" });
  });

  it("throws ApiError with the backend detail on a non-2xx response", async () => {
    mockFetchOnce({ detail: "article not found" }, 404);
    await expect(listArticles()).rejects.toBeInstanceOf(ApiError);
    await expect(listArticles()).rejects.toThrow("article not found");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test`
Expected: FAIL — `src/api.ts` does not exist yet.

- [ ] **Step 3: Implement `frontend/src/api.ts`**

```ts
export const BASE_URL = "http://127.0.0.1:8756";

export const KNOWN_KEYS = [
  "openalex_mailto",
  "semantic_scholar_key",
  "crossref_mailto",
  "deepseek_api_key",
] as const;

export const SOURCES = ["openalex", "semantic_scholar", "crossref", "doaj"] as const;

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

export interface Article {
  id: number;
  title: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  source: string;
  abstract: string | null;
  oa_pdf_url: string | null;
  pdf_path: string | null;
  extracted_text_ok: boolean;
  note: string | null;
  bib_key: string | null;
  analysis_json: string | null;
  created_at: string;
}

export interface ArticleIn {
  title: string;
  authors: string[];
  year?: number | null;
  doi?: string | null;
  source: string;
  abstract?: string | null;
  oa_pdf_url?: string | null;
}

export interface SearchResult {
  title: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  source: string;
  abstract: string | null;
  oa_pdf_url: string | null;
}

export interface SearchResponse {
  results: SearchResult[];
  errors: Record<string, string>;
}

export interface AnalyzeResponse {
  article_id: number;
  mode: string;
  result: string;
}

export interface ChatResponse {
  article_id: number;
  reply: string;
  messages: { role: string; content: string }[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init);
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body && typeof body === "object" && "detail" in body ? String((body as { detail: unknown }).detail) : `HTTP ${res.status}`;
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export function searchArticles(query: string, sources: string[]): Promise<SearchResponse> {
  return request("/search", jsonInit("POST", { query, sources }));
}

export function listArticles(): Promise<Article[]> {
  return request("/library", { method: "GET" });
}

export function getArticle(id: number): Promise<Article> {
  return request(`/library/${id}`, { method: "GET" });
}

export function addArticle(article: ArticleIn): Promise<Article> {
  return request("/library", jsonInit("POST", article));
}

export function downloadPdf(id: number): Promise<Article> {
  return request(`/library/${id}/download`, { method: "POST" });
}

export async function uploadPdf(id: number, file: File): Promise<Article> {
  const form = new FormData();
  form.append("file", file);
  return request(`/library/${id}/upload`, { method: "POST", body: form });
}

export function analyze(id: number, mode: "summary" | "metadata" | "verify"): Promise<AnalyzeResponse> {
  return request(`/library/${id}/analyze`, jsonInit("POST", { mode }));
}

export function sendChatMessage(id: number, message: string): Promise<ChatResponse> {
  return request(`/library/${id}/chat`, jsonInit("POST", { message }));
}

export async function exportBib(articleIds: number[]): Promise<string> {
  const res = await request<{ bib: string }>("/export/bib", jsonInit("POST", { article_ids: articleIds }));
  return res.bib;
}

export function listKeys(): Promise<Record<string, boolean>> {
  return request("/settings/keys", { method: "GET" });
}

export async function setKey(name: string, value: string): Promise<void> {
  await request(`/settings/keys/${name}`, jsonInit("PUT", { value }));
}

export async function deleteKey(name: string): Promise<void> {
  await request(`/settings/keys/${name}`, { method: "DELETE" });
}

export function testKey(name: string, value: string): Promise<{ ok: boolean; message: string }> {
  return request(`/settings/keys/${name}/test`, jsonInit("POST", { value }));
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test`
Expected: PASS (all `api.test.ts` cases green).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.ts frontend/tests/api.test.ts
git commit -m "feat(frontend): typed API client for the backend REST endpoints"
```

---

### Task 3: Router, backend-readiness gate, and app shell

**Files:**
- Create: `frontend/src/router.ts`
- Test: `frontend/tests/router.test.ts`
- Modify: `frontend/src/main.ts`

**Interfaces:**
- Consumes: `BASE_URL` from `api.ts` (Task 2).
- Produces:
  - `export function registerRoute(pattern: string, render: (params: Record<string, string>) => void): void` — `pattern` uses `:param` segments, e.g. `"/article/:id"`.
  - `export function navigate(path: string): void` — sets `location.hash` to `path`.
  - `export function startRouter(outlet: HTMLElement, notFound: () => void): void` — wires `hashchange`, does the first render.
  - Later views (Tasks 5-9) each call `registerRoute` once at import time.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/tests/router.test.ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import { registerRoute, navigate, startRouter } from "../src/router";

describe("router", () => {
  beforeEach(() => {
    location.hash = "";
  });

  it("invokes the matching route's render callback with path params", () => {
    const render = vi.fn();
    registerRoute("/article/:id", render);
    const outlet = document.createElement("div");
    startRouter(outlet, () => {});
    navigate("/article/42");
    expect(render).toHaveBeenCalledWith({ id: "42" });
  });

  it("falls back to notFound when no route matches", () => {
    const notFound = vi.fn();
    const outlet = document.createElement("div");
    startRouter(outlet, notFound);
    navigate("/does-not-exist");
    expect(notFound).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test`
Expected: FAIL — `src/router.ts` does not exist.

- [ ] **Step 3: Implement `frontend/src/router.ts`**

```ts
type RouteHandler = (params: Record<string, string>) => void;

interface Route {
  segments: string[];
  handler: RouteHandler;
}

const routes: Route[] = [];
let notFoundHandler: () => void = () => {};

export function registerRoute(pattern: string, render: RouteHandler): void {
  routes.push({ segments: pattern.split("/").filter(Boolean), handler: render });
}

export function navigate(path: string): void {
  location.hash = path;
}

function matchAndRender(): void {
  const path = location.hash.replace(/^#/, "") || "/";
  const pathSegments = path.split("/").filter(Boolean);

  for (const route of routes) {
    if (route.segments.length !== pathSegments.length) continue;
    const params: Record<string, string> = {};
    let matched = true;
    for (let i = 0; i < route.segments.length; i++) {
      const seg = route.segments[i];
      if (seg.startsWith(":")) {
        params[seg.slice(1)] = pathSegments[i];
      } else if (seg !== pathSegments[i]) {
        matched = false;
        break;
      }
    }
    if (matched) {
      route.handler(params);
      return;
    }
  }
  notFoundHandler();
}

export function startRouter(_outlet: HTMLElement, notFound: () => void): void {
  notFoundHandler = notFound;
  window.addEventListener("hashchange", matchAndRender);
  matchAndRender();
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test`
Expected: PASS.

- [ ] **Step 5: Implement the app shell in `frontend/src/main.ts`**

This replaces the Task 1 placeholder. It shows a "starting up" screen until the backend sidecar answers `/docs`, then renders the nav + router outlet. View modules don't exist yet (Tasks 5-9 add them) — leave the nav links pointing at routes that will 404 harmlessly until then; this file compiles and runs standalone.

```ts
import "./style.css";
import { BASE_URL } from "./api";
import { navigate, startRouter } from "./router";

const app = document.querySelector<HTMLDivElement>("#app")!;

async function waitForBackend(maxAttempts = 50, delayMs = 300): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const res = await fetch(`${BASE_URL}/docs`);
      if (res.ok) return true;
    } catch {
      // backend not up yet, keep polling
    }
    await new Promise((r) => setTimeout(r, delayMs));
  }
  return false;
}

function renderShell(): void {
  app.innerHTML = `
    <div id="backend-banner"></div>
    <nav>
      <a data-nav="/search">Ricerca</a>
      <a data-nav="/library">Libreria</a>
      <a data-nav="/settings">Impostazioni</a>
    </nav>
    <main id="outlet"></main>
  `;
  app.querySelectorAll<HTMLAnchorElement>("[data-nav]").forEach((a) => {
    a.addEventListener("click", () => navigate(a.dataset.nav!));
  });
  const outlet = document.querySelector<HTMLElement>("#outlet")!;
  startRouter(outlet, () => {
    outlet.innerHTML = "<p>Pagina non trovata.</p>";
  });
}

function renderStarting(): void {
  app.innerHTML = `<main><p>Avvio del motore di ricerca in corso...</p></main>`;
}

async function boot(): Promise<void> {
  renderStarting();
  const ready = await waitForBackend();
  if (!ready) {
    app.innerHTML = `<main><p class="banner banner-error">Impossibile contattare il backend su ${BASE_URL}. Riavvia l'applicazione.</p></main>`;
    return;
  }
  renderShell();
  navigate("/search");
}

boot();
```

- [ ] **Step 6: Run the full build to verify it compiles**

Run: `cd frontend && npm run build && npm run test`
Expected: both exit 0.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/router.ts frontend/src/main.ts frontend/tests/router.test.ts
git commit -m "feat(frontend): hash router, backend-readiness gate, app shell"
```

---

### Task 4: Rust sidecar lifecycle (spawn, kill, crash-restart)

**Files:**
- Modify: `frontend/src-tauri/src/main.rs`
- Modify: `frontend/src-tauri/Cargo.toml` (already has the deps from Task 1 — no change needed, this task just uses them)
- Create: `frontend/src/backendStatus.ts`

**Interfaces:**
- Produces: two Tauri events the frontend can listen for — `"backend-down"` (sidecar exited, one restart attempt in progress) and `"backend-crashed"` (sidecar exited a second time, restart exhausted). `backendStatus.ts` exports `subscribeToBackendStatus(onDown: () => void, onCrashed: () => void): void`.
- Produces: a `write_export` Tauri command — `invoke("write_export", { path: string, content: string })` — used by Task 10 (Export) to save the `.bib` file without fighting the fs-plugin's scope ACL.

This task cannot be verified end-to-end without a display (spawning the real sidecar and watching it crash needs a running window). Verify what's headlessly verifiable — `cargo build` compiles — and leave the rest as a documented manual check.

- [ ] **Step 1: Implement `frontend/src-tauri/src/main.rs`**

```rust
use std::sync::Mutex;
use tauri::{Emitter, Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

#[derive(Default)]
struct BackendProcess(Mutex<Option<CommandChild>>);

struct RestartCount(Mutex<u8>);

fn spawn_backend(app: tauri::AppHandle) {
    let sidecar = app
        .shell()
        .sidecar("litreview-backend")
        .expect("litreview-backend sidecar binary not bundled");
    let (mut rx, child) = sidecar.spawn().expect("failed to spawn litreview-backend");

    *app.state::<BackendProcess>().0.lock().unwrap() = Some(child);

    let app_for_events = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            if let CommandEvent::Terminated(_) = event {
                app_for_events.emit("backend-down", ()).ok();
                let restarts = app_for_events.state::<RestartCount>();
                let mut count = restarts.0.lock().unwrap();
                if *count == 0 {
                    *count += 1;
                    drop(count);
                    spawn_backend(app_for_events.clone());
                } else {
                    app_for_events.emit("backend-crashed", ()).ok();
                }
                break;
            }
        }
    });
}

#[tauri::command]
fn write_export(path: String, content: String) -> Result<(), String> {
    std::fs::write(path, content).map_err(|e| e.to_string())
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(BackendProcess::default())
        .manage(RestartCount(Mutex::new(0)))
        .invoke_handler(tauri::generate_handler![write_export])
        .setup(|app| {
            spawn_backend(app.handle().clone());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| {
        if let RunEvent::ExitRequested { .. } = event {
            if let Some(child) = app_handle.state::<BackendProcess>().0.lock().unwrap().take() {
                let _ = child.kill();
            }
        }
    });
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend/src-tauri && cargo build`
Expected: exits 0. (If the Tauri crate's exact method names have drifted from this plan's authoring-time knowledge, fix the compile errors here — they will be small signature mismatches, not architectural changes.)

- [ ] **Step 3: Implement `frontend/src/backendStatus.ts`**

```ts
import { listen } from "@tauri-apps/api/event";

export function subscribeToBackendStatus(onDown: () => void, onCrashed: () => void): void {
  listen("backend-down", () => onDown());
  listen("backend-crashed", () => onCrashed());
}
```

- [ ] **Step 4: Wire the banner into `frontend/src/main.ts`**

Add near the top of `renderShell()` in `frontend/src/main.ts`:

```ts
import { subscribeToBackendStatus } from "./backendStatus";
```

And inside `renderShell()`, after building the DOM:

```ts
subscribeToBackendStatus(
  () => {
    document.querySelector("#backend-banner")!.innerHTML =
      `<div class="banner banner-error">Il backend non risponde. Tentativo di riavvio in corso...</div>`;
  },
  () => {
    document.querySelector("#backend-banner")!.innerHTML =
      `<div class="banner banner-error">Il backend si è arrestato e non è stato possibile riavviarlo. Chiudi e riapri l'applicazione.</div>`;
  }
);
```

- [ ] **Step 5: Verify the frontend still builds**

Run: `cd frontend && npm run build`
Expected: exits 0.

- [ ] **Step 6: Manual verification checklist (record as a note, cannot run headlessly)**

> Run `npm run tauri dev` on a machine with a display and a built `backend/dist/litreview-backend-<os>` binary staged per Task 11. Confirm: (a) the app window opens and the "Avvio..." screen resolves once the backend answers `/docs`; (b) killing the sidecar process manually (e.g. `kill <pid>` of the spawned backend) shows the "riavvio in corso" banner and the app recovers; (c) closing the app window leaves no orphaned `litreview-backend` process running (`ps aux | grep litreview-backend`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src-tauri/src/main.rs frontend/src/backendStatus.ts frontend/src/main.ts
git commit -m "feat(frontend): sidecar lifecycle (spawn/kill/crash-restart) and status banner"
```

---

### Task 5: Settings screen + shared key-field widget

**Files:**
- Create: `frontend/src/views/keyField.ts`
- Create: `frontend/src/views/settings.ts`
- Test: `frontend/tests/helpers.test.ts` (add cases; file created here if it doesn't exist)
- Create: `frontend/src/helpers.ts`

**Interfaces:**
- Consumes: `listKeys`, `setKey`, `deleteKey`, `testKey`, `KNOWN_KEYS` from `api.ts` (Task 2); `registerRoute` from `router.ts` (Task 3).
- Produces:
  - `keyField.ts` exports `renderKeyField(container: HTMLElement, name: string, configured: boolean): void` — renders one key's input + Salva/Testa/Elimina row. Reused by Task 6 (onboarding).
  - `helpers.ts` exports `keyLabel(name: string): string` (e.g. `"deepseek_api_key"` → `"DeepSeek API key"`) — pure function, tested here since both Settings and Onboarding need identical labels and it's easy to get out of sync by hand.
  - `settings.ts` registers route `/settings` and has no other exports (view code, not imported elsewhere).

- [ ] **Step 1: Write the failing test for `keyLabel`**

```ts
// frontend/tests/helpers.test.ts
import { describe, it, expect } from "vitest";
import { keyLabel } from "../src/helpers";

describe("keyLabel", () => {
  it("maps known key names to display labels", () => {
    expect(keyLabel("openalex_mailto")).toBe("OpenAlex mailto");
    expect(keyLabel("semantic_scholar_key")).toBe("Semantic Scholar API key");
    expect(keyLabel("crossref_mailto")).toBe("Crossref mailto");
    expect(keyLabel("deepseek_api_key")).toBe("DeepSeek API key");
  });

  it("falls back to the raw name for unknown keys", () => {
    expect(keyLabel("mystery_key")).toBe("mystery_key");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test`
Expected: FAIL — `src/helpers.ts` does not exist.

- [ ] **Step 3: Implement `frontend/src/helpers.ts`**

```ts
const KEY_LABELS: Record<string, string> = {
  openalex_mailto: "OpenAlex mailto",
  semantic_scholar_key: "Semantic Scholar API key",
  crossref_mailto: "Crossref mailto",
  deepseek_api_key: "DeepSeek API key",
};

export function keyLabel(name: string): string {
  return KEY_LABELS[name] ?? name;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test`
Expected: PASS.

- [ ] **Step 5: Implement `frontend/src/views/keyField.ts`**

```ts
import { setKey, deleteKey, testKey } from "../api";
import { keyLabel } from "../helpers";

export function renderKeyField(container: HTMLElement, name: string, configured: boolean): void {
  const row = document.createElement("div");
  row.innerHTML = `
    <label>${keyLabel(name)} <span class="badge ${configured ? "badge-ok" : "badge-warn"}">${configured ? "configurato" : "non configurato"}</span></label>
    <input type="text" data-role="value" placeholder="${configured ? "•••••••• (invariato se lasci vuoto)" : ""}" />
    <button data-role="save">Salva</button>
    <button data-role="test">Testa connessione</button>
    <button data-role="delete">Elimina</button>
    <span data-role="message"></span>
  `;
  const input = row.querySelector<HTMLInputElement>("[data-role=value]")!;
  const message = row.querySelector<HTMLSpanElement>("[data-role=message]")!;

  row.querySelector("[data-role=save]")!.addEventListener("click", async () => {
    if (!input.value) return;
    await setKey(name, input.value);
    message.textContent = "Salvato.";
    input.value = "";
  });

  row.querySelector("[data-role=test]")!.addEventListener("click", async () => {
    if (!input.value) {
      message.textContent = "Inserisci un valore da testare.";
      return;
    }
    const result = await testKey(name, input.value);
    message.textContent = result.ok ? "Connessione riuscita." : `Errore: ${result.message}`;
  });

  row.querySelector("[data-role=delete]")!.addEventListener("click", async () => {
    await deleteKey(name);
    message.textContent = "Eliminata.";
  });

  container.appendChild(row);
}
```

- [ ] **Step 6: Implement `frontend/src/views/settings.ts`**

```ts
import { registerRoute } from "../router";
import { listKeys, KNOWN_KEYS } from "../api";
import { renderKeyField } from "./keyField";

registerRoute("/settings", async () => {
  const outlet = document.querySelector<HTMLElement>("#outlet")!;
  outlet.innerHTML = "<h2>Impostazioni</h2><div id=\"settings-keys\"></div>";
  const container = document.querySelector<HTMLElement>("#settings-keys")!;
  const configured = await listKeys();
  for (const name of KNOWN_KEYS) {
    renderKeyField(container, name, Boolean(configured[name]));
  }
});
```

- [ ] **Step 7: Register the settings view from `main.ts`**

Add to the top of `frontend/src/main.ts`: `import "./views/settings";`

- [ ] **Step 8: Verify build and tests**

Run: `cd frontend && npm run build && npm run test`
Expected: both exit 0.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/helpers.ts frontend/src/views/keyField.ts frontend/src/views/settings.ts frontend/tests/helpers.test.ts frontend/src/main.ts
git commit -m "feat(frontend): settings screen with per-key save/test/delete"
```

---

### Task 6: Onboarding wizard

**Files:**
- Create: `frontend/src/firstRun.ts`
- Test: `frontend/tests/firstRun.test.ts`
- Create: `frontend/src/views/onboarding.ts`
- Modify: `frontend/src/main.ts`

**Interfaces:**
- Consumes: `renderKeyField` from `keyField.ts` (Task 5); `KNOWN_KEYS` from `api.ts` (Task 2).
- Produces: `firstRun.ts` exports `isFirstRunDone(): boolean` and `markFirstRunDone(): void`, backed by `localStorage` key `"litreview_first_run_done"`. `main.ts`'s `boot()` checks `isFirstRunDone()` and navigates to `/onboarding` instead of `/search` when false.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/tests/firstRun.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { isFirstRunDone, markFirstRunDone } from "../src/firstRun";

describe("firstRun", () => {
  beforeEach(() => localStorage.clear());

  it("is false before markFirstRunDone is called", () => {
    expect(isFirstRunDone()).toBe(false);
  });

  it("is true after markFirstRunDone", () => {
    markFirstRunDone();
    expect(isFirstRunDone()).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test`
Expected: FAIL — `src/firstRun.ts` does not exist.

- [ ] **Step 3: Implement `frontend/src/firstRun.ts`**

```ts
const KEY = "litreview_first_run_done";

export function isFirstRunDone(): boolean {
  return localStorage.getItem(KEY) === "1";
}

export function markFirstRunDone(): void {
  localStorage.setItem(KEY, "1");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test`
Expected: PASS.

- [ ] **Step 5: Implement `frontend/src/views/onboarding.ts`**

```ts
import { registerRoute, navigate } from "../router";
import { KNOWN_KEYS } from "../api";
import { renderKeyField } from "./keyField";
import { markFirstRunDone } from "../firstRun";

registerRoute("/onboarding", () => {
  const outlet = document.querySelector<HTMLElement>("#outlet")!;
  outlet.innerHTML = `
    <h2>Benvenuto in LitReview</h2>
    <p>Configura le chiavi API per le fonti che vuoi usare. Puoi saltare questo passaggio e configurarle più tardi da Impostazioni.</p>
    <div id="onboarding-keys"></div>
    <button id="onboarding-skip">Salta, configuro dopo</button>
    <button id="onboarding-continue">Salva e continua</button>
  `;
  const container = document.querySelector<HTMLElement>("#onboarding-keys")!;
  for (const name of KNOWN_KEYS) {
    renderKeyField(container, name, false);
  }
  const finish = () => {
    markFirstRunDone();
    navigate("/search");
  };
  document.querySelector("#onboarding-skip")!.addEventListener("click", finish);
  document.querySelector("#onboarding-continue")!.addEventListener("click", finish);
});
```

`renderKeyField`'s own Salva button already persists each key via the API as the user fills it in; the wizard's "Salva e continua" just marks onboarding done and moves on — it doesn't need to re-save anything itself.

- [ ] **Step 6: Wire onboarding into the boot sequence**

In `frontend/src/main.ts`, add the import `import "./views/onboarding";` and `import { isFirstRunDone } from "./firstRun";`, then change the end of `boot()`:

```ts
  renderShell();
  navigate(isFirstRunDone() ? "/search" : "/onboarding");
```

- [ ] **Step 7: Verify build and tests**

Run: `cd frontend && npm run build && npm run test`
Expected: both exit 0.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/firstRun.ts frontend/src/views/onboarding.ts frontend/tests/firstRun.test.ts frontend/src/main.ts
git commit -m "feat(frontend): first-run onboarding wizard"
```

---

### Task 7: Search screen + configured-sources gating

**Files:**
- Create: `frontend/src/keysState.ts`
- Create: `frontend/src/views/search.ts`
- Test: `frontend/tests/helpers.test.ts` (add cases)
- Modify: `frontend/src/helpers.ts`
- Modify: `frontend/src/main.ts`

**Interfaces:**
- Consumes: `listKeys`, `searchArticles`, `addArticle`, `SOURCES`, `SearchResult` from `api.ts` (Task 2); `registerRoute` from `router.ts` (Task 3).
- Produces:
  - `keysState.ts` exports `async function getConfiguredSources(): Promise<Set<string>>` — maps the 3 source-specific keys (`openalex_mailto`, `semantic_scholar_key`, `crossref_mailto`) to source ids (`openalex`, `semantic_scholar`, `crossref`); `doaj` needs no key so it's always considered configured.
  - `helpers.ts` gains `export function buildSearchPayload(query: string, checked: string[]): { query: string; sources: string[] }` — pure, tested — trims the query and drops empty source lists down to `SOURCES` (search-all) only when the caller explicitly passes an empty checked list meaning "none disabled"; here it's a straight passthrough kept as its own function so the view stays thin and testable.

- [ ] **Step 1: Write the failing test**

```ts
// add to frontend/tests/helpers.test.ts
import { buildSearchPayload } from "../src/helpers";

describe("buildSearchPayload", () => {
  it("trims the query and passes through the checked sources", () => {
    expect(buildSearchPayload("  deep learning  ", ["openalex", "doaj"])).toEqual({
      query: "deep learning",
      sources: ["openalex", "doaj"],
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test`
Expected: FAIL — `buildSearchPayload` is not exported yet.

- [ ] **Step 3: Add `buildSearchPayload` to `frontend/src/helpers.ts`**

```ts
export function buildSearchPayload(query: string, checked: string[]): { query: string; sources: string[] } {
  return { query: query.trim(), sources: checked };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test`
Expected: PASS.

- [ ] **Step 5: Implement `frontend/src/keysState.ts`**

```ts
import { listKeys } from "./api";

const SOURCE_KEY: Record<string, string> = {
  openalex: "openalex_mailto",
  semantic_scholar: "semantic_scholar_key",
  crossref: "crossref_mailto",
};

export async function getConfiguredSources(): Promise<Set<string>> {
  const keys = await listKeys();
  const configured = new Set<string>(["doaj"]); // no key required
  for (const [source, keyName] of Object.entries(SOURCE_KEY)) {
    if (keys[keyName]) configured.add(source);
  }
  return configured;
}
```

- [ ] **Step 6: Implement `frontend/src/views/search.ts`**

```ts
import { registerRoute } from "../router";
import { searchArticles, addArticle, SOURCES, type SearchResult } from "../api";
import { getConfiguredSources } from "../keysState";
import { buildSearchPayload } from "../helpers";

registerRoute("/search", async () => {
  const outlet = document.querySelector<HTMLElement>("#outlet")!;
  const configured = await getConfiguredSources();

  outlet.innerHTML = `
    <h2>Ricerca</h2>
    <input id="search-query" placeholder="Query di ricerca" />
    <div id="search-sources">
      ${SOURCES.map((s) => `
        <label>
          <input type="checkbox" value="${s}" ${configured.has(s) ? "checked" : "disabled"} />
          ${s}${configured.has(s) ? "" : " (non configurato)"}
        </label>
      `).join("")}
    </div>
    <button id="search-submit">Cerca</button>
    <div id="search-errors"></div>
    <table id="search-results">
      <thead><tr><th>Titolo</th><th>Autori</th><th>Anno</th><th>Fonte</th><th>OA</th><th></th></tr></thead>
      <tbody></tbody>
    </table>
  `;

  document.querySelector("#search-submit")!.addEventListener("click", async () => {
    const query = document.querySelector<HTMLInputElement>("#search-query")!.value;
    const checked = Array.from(
      document.querySelectorAll<HTMLInputElement>("#search-sources input:checked")
    ).map((el) => el.value);
    const payload = buildSearchPayload(query, checked);
    if (!payload.query) return;

    const { results, errors } = await searchArticles(payload.query, payload.sources);

    const errorsBox = document.querySelector<HTMLElement>("#search-errors")!;
    errorsBox.innerHTML = Object.entries(errors)
      .map(([source, message]) => `<span class="badge badge-error">${source}: ${message}</span>`)
      .join(" ");

    const tbody = document.querySelector<HTMLElement>("#search-results tbody")!;
    tbody.innerHTML = "";
    results.forEach((r: SearchResult, i: number) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${r.title}</td>
        <td>${r.authors.join(", ")}</td>
        <td>${r.year ?? ""}</td>
        <td>${r.source}</td>
        <td>${r.oa_pdf_url ? '<span class="badge badge-ok">OA</span>' : ""}</td>
        <td><button data-add="${i}">Aggiungi a libreria</button></td>
      `;
      tbody.appendChild(tr);
      tr.querySelector("button")!.addEventListener("click", async (e) => {
        await addArticle({
          title: r.title,
          authors: r.authors,
          year: r.year,
          doi: r.doi,
          source: r.source,
          abstract: r.abstract,
          oa_pdf_url: r.oa_pdf_url,
        });
        (e.target as HTMLButtonElement).textContent = "Aggiunto";
        (e.target as HTMLButtonElement).disabled = true;
      });
    });
  });
});
```

- [ ] **Step 7: Register the search view from `main.ts`**

Add to `frontend/src/main.ts`: `import "./views/search";`

- [ ] **Step 8: Verify build and tests**

Run: `cd frontend && npm run build && npm run test`
Expected: both exit 0.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/keysState.ts frontend/src/views/search.ts frontend/src/helpers.ts frontend/tests/helpers.test.ts frontend/src/main.ts
git commit -m "feat(frontend): search screen with source gating and add-to-library"
```

---

### Task 8: Library screen (list, download, upload)

**Files:**
- Create: `frontend/src/views/library.ts`
- Test: `frontend/tests/helpers.test.ts` (add cases)
- Modify: `frontend/src/helpers.ts`
- Modify: `frontend/src/main.ts`

**Interfaces:**
- Consumes: `listArticles`, `downloadPdf`, `uploadPdf`, `Article` from `api.ts` (Task 2); `registerRoute`, `navigate` from `router.ts` (Task 3).
- Produces: `helpers.ts` gains `export function pdfStatusLabel(article: Pick<Article, "pdf_path" | "extracted_text_ok">): string` (`"Nessun PDF"` / `"PDF senza testo estraibile"` / `"PDF pronto"`) — pure, tested; used here and reused by Task 9's detail screen.

- [ ] **Step 1: Write the failing test**

```ts
// add to frontend/tests/helpers.test.ts
import { pdfStatusLabel } from "../src/helpers";

describe("pdfStatusLabel", () => {
  it("reports no PDF when pdf_path is null", () => {
    expect(pdfStatusLabel({ pdf_path: null, extracted_text_ok: false })).toBe("Nessun PDF");
  });

  it("reports unreadable text when downloaded but extraction failed", () => {
    expect(pdfStatusLabel({ pdf_path: "/x.pdf", extracted_text_ok: false })).toBe("PDF senza testo estraibile");
  });

  it("reports ready when text was extracted", () => {
    expect(pdfStatusLabel({ pdf_path: "/x.pdf", extracted_text_ok: true })).toBe("PDF pronto");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test`
Expected: FAIL.

- [ ] **Step 3: Add `pdfStatusLabel` to `frontend/src/helpers.ts`**

```ts
export function pdfStatusLabel(article: { pdf_path: string | null; extracted_text_ok: boolean }): string {
  if (!article.pdf_path) return "Nessun PDF";
  return article.extracted_text_ok ? "PDF pronto" : "PDF senza testo estraibile";
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test`
Expected: PASS.

- [ ] **Step 5: Implement `frontend/src/views/library.ts`**

```ts
import { registerRoute, navigate } from "../router";
import { listArticles, downloadPdf, uploadPdf, type Article } from "../api";
import { pdfStatusLabel } from "../helpers";

registerRoute("/library", async () => {
  const outlet = document.querySelector<HTMLElement>("#outlet")!;
  outlet.innerHTML = `
    <h2>Libreria</h2>
    <a href="#/export">Esporta .bib</a>
    <table id="library-table">
      <thead><tr><th>Titolo</th><th>Anno</th><th>Fonte</th><th>PDF</th><th></th></tr></thead>
      <tbody></tbody>
    </table>
  `;
  const articles = await listArticles();
  const tbody = document.querySelector<HTMLElement>("#library-table tbody")!;

  function renderRow(article: Article): void {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><a href="#/article/${article.id}">${article.title}</a></td>
      <td>${article.year ?? ""}</td>
      <td>${article.source}</td>
      <td>${pdfStatusLabel(article)}</td>
      <td>
        ${article.oa_pdf_url ? `<button data-download="${article.id}">Scarica PDF</button>` : `<input type="file" accept="application/pdf" data-upload="${article.id}" />`}
      </td>
    `;
    tbody.appendChild(tr);

    tr.querySelector("[data-download]")?.addEventListener("click", async () => {
      await downloadPdf(article.id);
      navigate("/library");
      registerAndRerender();
    });

    tr.querySelector("[data-upload]")?.addEventListener("change", async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      await uploadPdf(article.id, file);
      navigate("/library");
      registerAndRerender();
    });
  }

  function registerAndRerender(): void {
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  }

  articles.forEach(renderRow);
});
```

Note: `navigate("/library")` when already on `/library` does not fire `hashchange` (the hash doesn't change), so the explicit `registerAndRerender()` dispatch after download/upload is what actually refreshes the row statuses — without it the PDF status column would stay stale until the user manually navigates away and back.

- [ ] **Step 6: Register the library view from `main.ts`**

Add to `frontend/src/main.ts`: `import "./views/library";`

- [ ] **Step 7: Verify build and tests**

Run: `cd frontend && npm run build && npm run test`
Expected: both exit 0.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/library.ts frontend/src/helpers.ts frontend/tests/helpers.test.ts frontend/src/main.ts
git commit -m "feat(frontend): library screen with PDF download/upload"
```

---

### Task 9: Article detail — metadata, analysis, chat

**Files:**
- Create: `frontend/src/views/articleDetail.ts`
- Test: `frontend/tests/helpers.test.ts` (add cases)
- Modify: `frontend/src/helpers.ts`
- Modify: `frontend/src/main.ts`

**Interfaces:**
- Consumes: `getArticle`, `analyze`, `sendChatMessage`, `Article` from `api.ts` (Task 2); `registerRoute` from `router.ts` (Task 3); `pdfStatusLabel` from `helpers.ts` (Task 8).
- Produces: `helpers.ts` gains `export function canAnalyze(article: Pick<Article, "extracted_text_ok">): boolean` — pure, tested; gates the three analyze buttons and the chat input.

- [ ] **Step 1: Write the failing test**

```ts
// add to frontend/tests/helpers.test.ts
import { canAnalyze } from "../src/helpers";

describe("canAnalyze", () => {
  it("is false without extractable text", () => {
    expect(canAnalyze({ extracted_text_ok: false })).toBe(false);
  });

  it("is true with extractable text", () => {
    expect(canAnalyze({ extracted_text_ok: true })).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test`
Expected: FAIL.

- [ ] **Step 3: Add `canAnalyze` to `frontend/src/helpers.ts`**

```ts
export function canAnalyze(article: { extracted_text_ok: boolean }): boolean {
  return article.extracted_text_ok;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test`
Expected: PASS.

- [ ] **Step 5: Implement `frontend/src/views/articleDetail.ts`**

```ts
import { registerRoute } from "../router";
import { getArticle, analyze, sendChatMessage, type Article } from "../api";
import { pdfStatusLabel, canAnalyze } from "../helpers";

const MODES = [
  { id: "summary", label: "Riassunto" },
  { id: "metadata", label: "Estrazione metadati" },
  { id: "verify", label: "Verifica bibliografica" },
] as const;

registerRoute("/article/:id", async ({ id }) => {
  const outlet = document.querySelector<HTMLElement>("#outlet")!;
  const article: Article = await getArticle(Number(id));
  const analysis: Record<string, string> = article.analysis_json ? JSON.parse(article.analysis_json) : {};
  const ready = canAnalyze(article);

  outlet.innerHTML = `
    <h2>${article.title}</h2>
    <p>${article.authors.join(", ")} — ${article.year ?? "anno sconosciuto"}</p>
    <p>${pdfStatusLabel(article)}</p>
    ${!ready ? '<p class="banner banner-error">Nessun testo estraibile dal PDF: analisi e chat non disponibili.</p>' : ""}

    <h3>Analisi</h3>
    <div id="analysis-buttons">
      ${MODES.map((m) => `<button data-mode="${m.id}" ${ready ? "" : "disabled"}>${m.label}</button>`).join("")}
    </div>
    <div id="analysis-results">
      ${MODES.map((m) => `<section><h4>${m.label}</h4><pre data-result="${m.id}">${analysis[m.id] ?? "(non ancora eseguita)"}</pre></section>`).join("")}
    </div>

    <h3>Chat</h3>
    <div id="chat-messages"></div>
    <input id="chat-input" ${ready ? "" : "disabled"} placeholder="Fai una domanda sull'articolo" />
    <button id="chat-send" ${ready ? "" : "disabled"}>Invia</button>
  `;

  document.querySelectorAll<HTMLButtonElement>("#analysis-buttons button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const mode = btn.dataset.mode as "summary" | "metadata" | "verify";
      btn.disabled = true;
      try {
        const res = await analyze(article.id, mode);
        document.querySelector(`[data-result="${mode}"]`)!.textContent = res.result;
      } finally {
        btn.disabled = false;
      }
    });
  });

  const chatMessages = document.querySelector<HTMLElement>("#chat-messages")!;
  function renderChat(messages: { role: string; content: string }[]): void {
    chatMessages.innerHTML = messages
      .map((m) => `<p><strong>${m.role === "user" ? "Tu" : "LitReview"}:</strong> ${m.content}</p>`)
      .join("");
  }

  document.querySelector("#chat-send")!.addEventListener("click", async () => {
    const input = document.querySelector<HTMLInputElement>("#chat-input")!;
    if (!input.value) return;
    const message = input.value;
    input.value = "";
    const res = await sendChatMessage(article.id, message);
    renderChat(res.messages);
  });
});
```

- [ ] **Step 6: Register the article detail view from `main.ts`**

Add to `frontend/src/main.ts`: `import "./views/articleDetail";`

- [ ] **Step 7: Verify build and tests**

Run: `cd frontend && npm run build && npm run test`
Expected: both exit 0.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/articleDetail.ts frontend/src/helpers.ts frontend/tests/helpers.test.ts frontend/src/main.ts
git commit -m "feat(frontend): article detail screen with analysis and chat"
```

---

### Task 10: Export screen

**Files:**
- Create: `frontend/src/views/export.ts`
- Test: `frontend/tests/helpers.test.ts` (add cases)
- Modify: `frontend/src/helpers.ts`
- Modify: `frontend/src/main.ts`

**Interfaces:**
- Consumes: `listArticles`, `exportBib`, `Article` from `api.ts` (Task 2); `registerRoute` from `router.ts` (Task 3); `write_export` Tauri command from `main.rs` (Task 4); `save` from `@tauri-apps/plugin-dialog`.
- Produces: `helpers.ts` gains `export function buildExportPayload(checkedIds: string[]): number[]` (parses the checkbox `value` strings to numbers) — pure, tested.

- [ ] **Step 1: Write the failing test**

```ts
// add to frontend/tests/helpers.test.ts
import { buildExportPayload } from "../src/helpers";

describe("buildExportPayload", () => {
  it("parses checked id strings to numbers", () => {
    expect(buildExportPayload(["1", "42", "7"])).toEqual([1, 42, 7]);
  });

  it("returns an empty array for no selection", () => {
    expect(buildExportPayload([])).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test`
Expected: FAIL.

- [ ] **Step 3: Add `buildExportPayload` to `frontend/src/helpers.ts`**

```ts
export function buildExportPayload(checkedIds: string[]): number[] {
  return checkedIds.map(Number);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test`
Expected: PASS.

- [ ] **Step 5: Implement `frontend/src/views/export.ts`**

```ts
import { registerRoute } from "../router";
import { listArticles, exportBib } from "../api";
import { buildExportPayload } from "../helpers";
import { save } from "@tauri-apps/plugin-dialog";
import { invoke } from "@tauri-apps/api/core";

registerRoute("/export", async () => {
  const outlet = document.querySelector<HTMLElement>("#outlet")!;
  const articles = await listArticles();

  outlet.innerHTML = `
    <h2>Esporta .bib</h2>
    <ul id="export-list">
      ${articles.map((a) => `<li><label><input type="checkbox" value="${a.id}" /> ${a.title}</label></li>`).join("")}
    </ul>
    <button id="export-submit">Esporta .bib</button>
    <p id="export-message"></p>
  `;

  document.querySelector("#export-submit")!.addEventListener("click", async () => {
    const checked = Array.from(
      document.querySelectorAll<HTMLInputElement>("#export-list input:checked")
    ).map((el) => el.value);
    const ids = buildExportPayload(checked);
    if (ids.length === 0) return;

    const bib = await exportBib(ids);
    const path = await save({ filters: [{ name: "BibTeX", extensions: ["bib"] }] });
    if (!path) return;
    await invoke("write_export", { path, content: bib });
    document.querySelector("#export-message")!.textContent = `Salvato in ${path}`;
  });
});
```

- [ ] **Step 6: Register the export view from `main.ts`**

Add to `frontend/src/main.ts`: `import "./views/export";`

- [ ] **Step 7: Verify build and tests**

Run: `cd frontend && npm run build && npm run test`
Expected: both exit 0.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/export.ts frontend/src/helpers.ts frontend/tests/helpers.test.ts frontend/src/main.ts
git commit -m "feat(frontend): export screen with native save dialog"
```

---

### Task 11: Sidecar packaging script + local dev instructions

**Files:**
- Create: `frontend/scripts/prepare-sidecar.mjs`
- Modify: `frontend/package.json` (add `prepare-sidecar` script)
- Modify: `frontend/README.md` (create if missing)

**Interfaces:**
- Consumes: `backend/dist/litreview-backend-<os>[.exe]`, already produced by `backend/packaging/litreview.spec` (existing, unmodified by this plan).
- Produces: `frontend/src-tauri/binaries/litreview-backend-<target-triple>[.exe]`, matching what `tauri.conf.json`'s `externalBin: ["binaries/litreview-backend"]` (Task 1) expects at bundle/run time.

- [ ] **Step 1: Implement `frontend/scripts/prepare-sidecar.mjs`**

```js
import { execSync } from "node:child_process";
import { copyFileSync, chmodSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const SOURCE_BY_PLATFORM = {
  win32: "litreview-backend-windows.exe",
  darwin: "litreview-backend-macos",
  linux: "litreview-backend-linux",
};

const sourceName = SOURCE_BY_PLATFORM[process.platform];
if (!sourceName) {
  console.error(`Unsupported platform: ${process.platform}`);
  process.exit(1);
}

const sourcePath = join("..", "backend", "dist", sourceName);
if (!existsSync(sourcePath)) {
  console.error(
    `Missing ${sourcePath}. Build the backend first:\n  cd backend && pip install -e ".[dev]" pyinstaller && pyinstaller --distpath dist --workpath build packaging/litreview.spec`
  );
  process.exit(1);
}

const targetTriple = execSync("rustc --print host-tuple").toString().trim();
const extension = process.platform === "win32" ? ".exe" : "";
const destDir = join("src-tauri", "binaries");
mkdirSync(destDir, { recursive: true });
const destPath = join(destDir, `litreview-backend-${targetTriple}${extension}`);

copyFileSync(sourcePath, destPath);
if (process.platform !== "win32") {
  chmodSync(destPath, 0o755);
}
console.log(`Sidecar staged at ${destPath}`);
```

- [ ] **Step 2: Add the script to `frontend/package.json`**

In the `"scripts"` block, add: `"prepare-sidecar": "node scripts/prepare-sidecar.mjs"`.

- [ ] **Step 3: Create `frontend/README.md`**

```markdown
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
```

- [ ] **Step 4: Verify the script runs (will fail without a built backend — that's expected and correct)**

Run: `cd frontend && node scripts/prepare-sidecar.mjs`
Expected: exits 1 with the "Missing ... Build the backend first" message, unless `backend/dist/` already has a binary from a previous local build — either outcome (clean failure message, or a successful copy) is correct; a silent crash or wrong path is not.

- [ ] **Step 5: Commit**

```bash
git add frontend/scripts/prepare-sidecar.mjs frontend/package.json frontend/README.md
git commit -m "feat(frontend): sidecar staging script and local dev instructions"
```

---

### Task 12: CI — build desktop installers per OS

**Files:**
- Modify: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: the existing `build-windows`, `build-macos`, `build-linux` jobs' `*-binary` artifacts (already produced, unmodified by this plan) and `frontend/scripts/prepare-sidecar.mjs` (Task 11).
- Produces: three new artifacts (`desktop-windows`, `desktop-macos`, `desktop-linux`) containing the Tauri-bundled installers, added to the existing `release` job's asset list.

This task only touches CI config — nothing to run locally beyond `git diff` review. It's verified by watching the workflow run after a tag push (same pattern as the macOS dmg change earlier in this session).

- [ ] **Step 1: Add three new jobs to `.github/workflows/release.yml`**, after the existing `build-linux` job and before the `release` job:

```yaml
  build-desktop-windows:
    needs: build-windows
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: windows-binary
          path: backend/dist
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - uses: dtolnay/rust-toolchain@stable
      - name: Prepare sidecar
        working-directory: frontend
        run: npm run prepare-sidecar
      - name: Install frontend deps
        working-directory: frontend
        run: npm ci
      - name: Build installer
        working-directory: frontend
        run: npm run tauri build
      - uses: actions/upload-artifact@v4
        with:
          name: desktop-windows
          path: |
            frontend/src-tauri/target/release/bundle/msi/*.msi
            frontend/src-tauri/target/release/bundle/nsis/*.exe

  build-desktop-macos:
    needs: build-macos
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: macos-binary
          path: backend/dist
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - uses: dtolnay/rust-toolchain@stable
        with:
          targets: aarch64-apple-darwin
      - name: Prepare sidecar
        working-directory: frontend
        run: npm run prepare-sidecar
      - name: Install frontend deps
        working-directory: frontend
        run: npm ci
      - name: Build installer
        working-directory: frontend
        run: npm run tauri build -- --target aarch64-apple-darwin
      - uses: actions/upload-artifact@v4
        with:
          name: desktop-macos
          path: frontend/src-tauri/target/aarch64-apple-darwin/release/bundle/dmg/*.dmg

  build-desktop-linux:
    needs: build-linux
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: linux-binary
          path: backend/dist
      - name: Install Tauri Linux dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf xdg-utils
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - uses: dtolnay/rust-toolchain@stable
      - name: Prepare sidecar
        working-directory: frontend
        run: npm run prepare-sidecar
      - name: Install frontend deps
        working-directory: frontend
        run: npm ci
      - name: Build installer
        working-directory: frontend
        run: npm run tauri build -- --bundles deb,appimage
      - uses: actions/upload-artifact@v4
        with:
          name: desktop-linux
          path: |
            frontend/src-tauri/target/release/bundle/deb/*.deb
            frontend/src-tauri/target/release/bundle/appimage/*.AppImage
```

- [ ] **Step 2: Update the `release` job's `needs:` list**

Change:
```yaml
  release:
    needs: [build-windows, build-macos, build-linux]
```
to:
```yaml
  release:
    needs: [build-windows, build-macos, build-linux, build-desktop-windows, build-desktop-macos, build-desktop-linux]
```

- [ ] **Step 3: Add the new artifact downloads and release files**

After the existing `macos-dmg` download step in the `release` job, add:

```yaml
      - uses: actions/download-artifact@v4
        with:
          pattern: "desktop-*"
          path: artifacts
          merge-multiple: true
```

And extend the `softprops/action-gh-release@v2` step's `files:` block to also include:
```yaml
            artifacts/*.msi
            artifacts/*.exe
            artifacts/*.dmg
            artifacts/*.deb
            artifacts/*.AppImage
```

Note: `artifacts/*.exe` here is fine alongside the already-listed `artifacts/litreview-backend-windows.exe` — they're different files in the same flattened directory (the raw PyInstaller exe plus the NSIS installer exe, if NSIS produces one instead of/alongside the MSI); `softprops/action-gh-release` uploads whatever the globs match and does not error on an already-matched exact filename appearing again via a glob.

- [ ] **Step 4: Validate the YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))" && echo OK`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci(release): build Tauri desktop installers for Windows/macOS/Linux"
```

---

### Task 13: Docs — document the desktop app as the recommended install path

**Files:**
- Modify: `README.md`
- Modify: `backend/README.md`

**Interfaces:** none — documentation only, additive to the existing one-click-launcher instructions (do not remove them; the raw backend + launcher-script flow keeps working as a lighter-weight alternative for users who don't want a full desktop install).

- [ ] **Step 1: Add a "Desktop app" section to `README.md`**, above the existing "One-click install (end users)" section:

```markdown
## Desktop app (recommended)

Download the installer for your OS from the [latest release](https://github.com/nugh75/Ricerca-scientifica/releases):

| OS | Installer |
|---|---|
| Windows | `.msi` (or `.exe`) |
| macOS | `.dmg` (Apple Silicon only) |
| Linux | `.deb` or `.AppImage` |

Install and launch like any other desktop app — it starts the backend for you automatically and shows a graphical UI for search, library, PDF analysis, and `.bib` export. No terminal needed.

Prefer a lighter footprint with just the API and no GUI? See the raw backend launcher scripts below.
```

- [ ] **Step 2: Update the `## Status` section's frontend line**

Find:
```markdown
- **Desktop shell** (Tauri): planned. The backend is designed to run as a
  sidecar (`externalBin`); see
  [docs/superpowers/specs/2026-08-17-literature-review-app-design.md](docs/superpowers/specs/2026-08-17-literature-review-app-design.md).
```
Replace with:
```markdown
- **Desktop shell** (Tauri): implemented, see [frontend/](frontend/) and
  [docs/superpowers/specs/2026-08-17-literature-review-app-design.md](docs/superpowers/specs/2026-08-17-literature-review-app-design.md).
```

- [ ] **Step 3: Add a short pointer in `backend/README.md`**

At the top of the "Installazione one-click (release GitHub)" section, add:

```markdown
> Per la maggior parte degli utenti conviene installare l'app desktop
> (`.msi`/`.dmg`/`.deb`/`.AppImage`, vedi il README principale) invece del
> solo backend qui sotto — ha già un'interfaccia grafica.
```

- [ ] **Step 4: Commit**

```bash
git add README.md backend/README.md
git commit -m "docs: point users at the desktop app as the recommended install path"
```

---

## Post-plan manual verification (cannot be automated in this environment)

After Task 4 and again after Task 13, on a machine with a display:
1. `cd frontend && npm run prepare-sidecar && npm install && npm run tauri dev`
2. Walk the golden path: onboarding → skip → search (with at least one source configured) → add result to library → download or upload a PDF → run each analysis mode → send a chat message → export selected articles to a `.bib` file and confirm its contents.
3. Confirm closing the window leaves no orphaned `litreview-backend` process.
4. After a tag push, download the real installer artifacts from the GitHub Release and confirm they install and launch on each OS.
