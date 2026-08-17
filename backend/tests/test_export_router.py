def _add_article(client, title, authors, year=2020, doi=None):
    resp = client.post(
        "/library",
        json={
            "title": title, "authors": authors, "year": year, "doi": doi,
            "source": "openalex", "abstract": None, "oa_pdf_url": None,
        },
    )
    return resp.json()


def test_export_bib_returns_bibtex_for_selected_articles(client):
    a1 = _add_article(client, "Paper One", ["Jane Smith"])
    _add_article(client, "Paper Two", ["John Doe"])  # not selected

    resp = client.post("/export/bib", json={"article_ids": [a1["id"]]})
    assert resp.status_code == 200
    bib = resp.json()["bib"]
    assert "@article{Smith2020Paper" in bib
    assert "Paper Two" not in bib


def test_export_bib_skips_missing_ids(client):
    a1 = _add_article(client, "Paper One", ["Jane Smith"])
    resp = client.post("/export/bib", json={"article_ids": [a1["id"], 999]})
    assert resp.status_code == 200
    assert resp.json()["bib"].count("@article") == 1


def test_export_bib_empty_selection_returns_empty_string(client):
    resp = client.post("/export/bib", json={"article_ids": []})
    assert resp.status_code == 200
    assert resp.json()["bib"] == ""
