const KEY_LABELS: Record<string, string> = {
  openalex_mailto: "OpenAlex mailto",
  semantic_scholar_key: "Semantic Scholar API key",
  crossref_mailto: "Crossref mailto",
  deepseek_api_key: "DeepSeek API key",
};

export function keyLabel(name: string): string {
  return KEY_LABELS[name] ?? name;
}
