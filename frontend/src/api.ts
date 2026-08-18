const DEFAULT_PORT = 8756;
let baseUrl = `http://127.0.0.1:${DEFAULT_PORT}`;

// The backend picks a free port at startup, so the base URL is only known once
// it has announced itself. Until then the default is the best guess we have.
export function getBaseUrl(): string {
  return baseUrl;
}

export function setBackendPort(port: number): void {
  baseUrl = `http://127.0.0.1:${port}`;
}

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
  const res = await fetch(`${getBaseUrl()}${path}`, init);
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

export async function testKey(name: string, value: string): Promise<{ ok: boolean; message: string }> {
  const res = await request<{ ok: boolean; message: string }>(`/settings/keys/${name}/test`, jsonInit("POST", { value }));
  return { ok: res.ok, message: res.message };
}
