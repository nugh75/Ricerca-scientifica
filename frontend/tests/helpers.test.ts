import { describe, it, expect } from "vitest";
import { keyLabel, buildSearchPayload, pdfStatusLabel, canAnalyze, buildExportPayload, escapeHtml } from "../src/helpers";

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

describe("canAnalyze", () => {
  it("is false without extractable text", () => {
    expect(canAnalyze({ extracted_text_ok: false })).toBe(false);
  });

  it("is true with extractable text", () => {
    expect(canAnalyze({ extracted_text_ok: true })).toBe(true);
  });
});

describe("buildExportPayload", () => {
  it("parses checked id strings to numbers", () => {
    expect(buildExportPayload(["1", "42", "7"])).toEqual([1, 42, 7]);
  });

  it("returns an empty array for no selection", () => {
    expect(buildExportPayload([])).toEqual([]);
  });
});

describe("escapeHtml", () => {
  it("escapes HTML special characters", () => {
    expect(escapeHtml("<script>alert(1)</script>")).toBe("&lt;script&gt;alert(1)&lt;/script&gt;");
  });

  it("escapes ampersands before other entities are introduced (no double-encoding)", () => {
    expect(escapeHtml("Tom & Jerry")).toBe("Tom &amp; Jerry");
  });

  it("escapes quotes", () => {
    expect(escapeHtml(`He said "hi" and 'bye'`)).toBe("He said &quot;hi&quot; and &#39;bye&#39;");
  });

  it("leaves plain text unchanged", () => {
    expect(escapeHtml("plain text 123")).toBe("plain text 123");
  });
});
