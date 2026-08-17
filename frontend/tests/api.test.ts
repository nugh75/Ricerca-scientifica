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
