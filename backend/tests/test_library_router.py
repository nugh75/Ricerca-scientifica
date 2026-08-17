import io

from litreview import pdf_utils
from litreview.routers import library_router


def _add_sample_article(client, oa_pdf_url=None):
    resp = client.post(
        "/library",
        json={
            "title": "Paper One",
            "authors": ["Jane Smith"],
            "year": 2020,
            "doi": "10.1/a",
            "source": "openalex",
            "abstract": "An abstract.",
            "oa_pdf_url": oa_pdf_url,
        },
    )
    assert resp.status_code == 200
    return resp.json()


def test_add_and_list_article(client):
    created = _add_sample_article(client)
    assert created["title"] == "Paper One"
    assert created["authors"] == ["Jane Smith"]

    resp = client.get("/library")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_article_by_id(client):
    created = _add_sample_article(client)
    resp = client.get(f"/library/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_missing_article_returns_404(client):
    resp = client.get("/library/999")
    assert resp.status_code == 404


def test_download_pdf_without_oa_url_returns_400(client):
    created = _add_sample_article(client, oa_pdf_url=None)
    resp = client.post(f"/library/{created['id']}/download")
    assert resp.status_code == 400


def test_download_pdf_success_updates_article(client, monkeypatch, tmp_path):
    monkeypatch.setattr(library_router, "PDF_DIR", tmp_path)
    monkeypatch.setattr(
        pdf_utils, "download_pdf", lambda url, dest: dest.write_bytes(b"x") or dest
    )
    monkeypatch.setattr(pdf_utils, "extract_text", lambda path, max_pages=30: "a" * 300)
    monkeypatch.setattr(pdf_utils, "has_extractable_text", lambda text: True)

    created = _add_sample_article(client, oa_pdf_url="https://example.org/a.pdf")
    resp = client.post(f"/library/{created['id']}/download")
    assert resp.status_code == 200
    data = resp.json()
    assert data["extracted_text_ok"] is True
    assert data["pdf_path"] is not None


def test_download_pdf_failure_returns_502(client, monkeypatch):
    def raise_download_error(url, dest):
        raise pdf_utils.PdfDownloadError("network error")

    monkeypatch.setattr(pdf_utils, "download_pdf", raise_download_error)
    created = _add_sample_article(client, oa_pdf_url="https://example.org/a.pdf")
    resp = client.post(f"/library/{created['id']}/download")
    assert resp.status_code == 502


def test_upload_pdf_updates_article(client, monkeypatch, tmp_path):
    monkeypatch.setattr(library_router, "PDF_DIR", tmp_path)
    monkeypatch.setattr(pdf_utils, "extract_text", lambda path, max_pages=30: "a" * 300)
    monkeypatch.setattr(pdf_utils, "has_extractable_text", lambda text: True)

    created = _add_sample_article(client)
    resp = client.post(
        f"/library/{created['id']}/upload",
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 content"), "application/pdf")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["extracted_text_ok"] is True


def test_upload_pdf_missing_article_returns_404(client, tmp_path):
    resp = client.post(
        "/library/999/upload",
        files={"file": ("test.pdf", io.BytesIO(b"x"), "application/pdf")},
    )
    assert resp.status_code == 404
