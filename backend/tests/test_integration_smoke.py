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
