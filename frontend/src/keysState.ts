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
