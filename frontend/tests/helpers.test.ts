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
