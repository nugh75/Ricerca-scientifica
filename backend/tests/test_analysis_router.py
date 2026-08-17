import json

from litreview import keys, pdf_utils
from litreview.routers import analysis_router


class FakeDeepSeekClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def analyze(self, mode, text, *, title="", authors=None, year=None):
        return f"analysis:{mode}"

    def chat(self, text, messages):
        return "assistant reply"


def _add_article_with_pdf(client, conn_monkeypatch=None):
    resp = client.post(
        "/library",
        json={
            "title": "Paper One", "authors": ["Jane Smith"], "year": 2020,
            "doi": "10.1/a", "source": "openalex", "abstract": "abs",
            "oa_pdf_url": "https://example.org/a.pdf",
        },
    )
    article = resp.json()
    return article


def test_analyze_without_key_returns_400(client, monkeypatch):
    monkeypatch.setattr(keys, "get_key", lambda name: None)
    article = _add_article_with_pdf(client)
    resp = client.post(f"/library/{article['id']}/analyze", json={"mode": "summary"})
    assert resp.status_code == 400


def test_analyze_keyring_unavailable_returns_503(client, monkeypatch):
    def raise_unavailable(name):
        raise keys.KeyringUnavailableError("no backend")

    monkeypatch.setattr(keys, "get_key", raise_unavailable)
    article = _add_article_with_pdf(client)
    resp = client.post(f"/library/{article['id']}/analyze", json={"mode": "summary"})
    assert resp.status_code == 503


def test_analyze_without_pdf_returns_400(client, monkeypatch):
    monkeypatch.setattr(keys, "get_key", lambda name: "sk-test")
    article = _add_article_with_pdf(client)
    resp = client.post(f"/library/{article['id']}/analyze", json={"mode": "summary"})
    assert resp.status_code == 400


def test_analyze_success_stores_and_returns_result(client, monkeypatch, tmp_path):
    monkeypatch.setattr(keys, "get_key", lambda name: "sk-test")
    monkeypatch.setattr(analysis_router, "DeepSeekClient", FakeDeepSeekClient)
    monkeypatch.setattr(pdf_utils, "extract_text", lambda path, max_pages=30: "full text")

    article = _add_article_with_pdf(client)
    # simulate a completed download by writing directly through the library router's DB
    from litreview.routers import library_router
    monkeypatch.setattr(library_router, "PDF_DIR", tmp_path)
    monkeypatch.setattr(
        pdf_utils, "download_pdf", lambda url, dest: dest.write_bytes(b"x") or dest
    )
    monkeypatch.setattr(pdf_utils, "has_extractable_text", lambda text: True)
    client.post(f"/library/{article['id']}/download")

    resp = client.post(f"/library/{article['id']}/analyze", json={"mode": "summary"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] == "analysis:summary"

    stored = client.get(f"/library/{article['id']}").json()
    assert json.loads(stored["analysis_json"])["summary"] == "analysis:summary"


def test_analyze_unmapped_article_returns_404(client, monkeypatch):
    monkeypatch.setattr(keys, "get_key", lambda name: "sk-test")
    resp = client.post("/library/999/analyze", json={"mode": "summary"})
    assert resp.status_code == 404


def test_analyze_invalid_mode_returns_400(client, monkeypatch, tmp_path):
    class RaisingFakeDeepSeekClient:
        def __init__(self, api_key):
            pass

        def analyze(self, mode, text, **kwargs):
            raise ValueError(f"unknown mode: {mode}")

    monkeypatch.setattr(keys, "get_key", lambda name: "sk-test")
    monkeypatch.setattr(analysis_router, "DeepSeekClient", RaisingFakeDeepSeekClient)
    monkeypatch.setattr(pdf_utils, "extract_text", lambda path, max_pages=30: "full text")
    from litreview.routers import library_router
    monkeypatch.setattr(library_router, "PDF_DIR", tmp_path)
    monkeypatch.setattr(pdf_utils, "download_pdf", lambda url, dest: dest.write_bytes(b"x") or dest)
    monkeypatch.setattr(pdf_utils, "has_extractable_text", lambda text: True)

    article = _add_article_with_pdf(client)
    client.post(f"/library/{article['id']}/download")

    resp = client.post(f"/library/{article['id']}/analyze", json={"mode": "not_a_real_mode"})
    assert resp.status_code == 400


def test_chat_creates_session_and_returns_reply(client, monkeypatch, tmp_path):
    monkeypatch.setattr(keys, "get_key", lambda name: "sk-test")
    monkeypatch.setattr(analysis_router, "DeepSeekClient", FakeDeepSeekClient)
    monkeypatch.setattr(pdf_utils, "extract_text", lambda path, max_pages=30: "full text")

    from litreview.routers import library_router
    monkeypatch.setattr(library_router, "PDF_DIR", tmp_path)
    monkeypatch.setattr(
        pdf_utils, "download_pdf", lambda url, dest: dest.write_bytes(b"x") or dest
    )
    monkeypatch.setattr(pdf_utils, "has_extractable_text", lambda text: True)

    article = _add_article_with_pdf(client)
    client.post(f"/library/{article['id']}/download")

    resp = client.post(f"/library/{article['id']}/chat", json={"message": "What is the sample?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "assistant reply"
    assert len(data["messages"]) == 2


def test_chat_second_call_updates_existing_session(client, monkeypatch, tmp_path):
    monkeypatch.setattr(keys, "get_key", lambda name: "sk-test")
    monkeypatch.setattr(analysis_router, "DeepSeekClient", FakeDeepSeekClient)
    monkeypatch.setattr(pdf_utils, "extract_text", lambda path, max_pages=30: "full text")
    from litreview.routers import library_router
    monkeypatch.setattr(library_router, "PDF_DIR", tmp_path)
    monkeypatch.setattr(pdf_utils, "download_pdf", lambda url, dest: dest.write_bytes(b"x") or dest)
    monkeypatch.setattr(pdf_utils, "has_extractable_text", lambda text: True)

    article = _add_article_with_pdf(client)
    client.post(f"/library/{article['id']}/download")

    client.post(f"/library/{article['id']}/chat", json={"message": "First question"})
    resp = client.post(f"/library/{article['id']}/chat", json={"message": "Second question"})
    assert resp.status_code == 200
    assert len(resp.json()["messages"]) == 4


def test_chat_without_pdf_returns_400(client, monkeypatch):
    monkeypatch.setattr(keys, "get_key", lambda name: "sk-test")
    article = _add_article_with_pdf(client)
    resp = client.post(f"/library/{article['id']}/chat", json={"message": "hi"})
    assert resp.status_code == 400
