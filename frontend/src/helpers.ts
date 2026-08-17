const KEY_LABELS: Record<string, string> = {
  openalex_mailto: "OpenAlex mailto",
  semantic_scholar_key: "Semantic Scholar API key",
  crossref_mailto: "Crossref mailto",
  deepseek_api_key: "DeepSeek API key",
};

export function keyLabel(name: string): string {
  return KEY_LABELS[name] ?? name;
}

export function buildSearchPayload(query: string, checked: string[]): { query: string; sources: string[] } {
  return { query: query.trim(), sources: checked };
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function pdfStatusLabel(article: { pdf_path: string | null; extracted_text_ok: boolean }): string {
  if (!article.pdf_path) return "Nessun PDF";
  return article.extracted_text_ok ? "PDF pronto" : "PDF senza testo estraibile";
}

export function canAnalyze(article: { extracted_text_ok: boolean }): boolean {
  return article.extracted_text_ok;
}
