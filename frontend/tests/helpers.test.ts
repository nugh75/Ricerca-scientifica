import { describe, it, expect } from "vitest";
import { keyLabel, buildSearchPayload, pdfStatusLabel } from "../src/helpers";

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

describe("buildSearchPayload", () => {
  it("trims the query and passes through the checked sources", () => {
    expect(buildSearchPayload("  deep learning  ", ["openalex", "doaj"])).toEqual({
      query: "deep learning",
      sources: ["openalex", "doaj"],
    });
  });
});

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
