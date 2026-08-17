from unittest.mock import Mock, patch

import requests

from litreview.api_clients import doaj
from litreview.api_clients.base import SourceError

SAMPLE_RESPONSE = {
    "results": [
        {
            "bibjson": {
                "title": "Open Access Study",
                "author": [{"name": "Rosa Park"}],
                "year": "2022",
                "abstract": "About open access.",
                "identifier": [{"type": "doi", "id": "10.4/oa"}],
                "link": [{"type": "fulltext", "url": "https://example.org/oa.pdf"}],
            }
        }
    ]
}


def test_search_normalizes_results():
    mock_resp = Mock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status.return_value = None
    with patch.object(doaj.requests, "get", return_value=mock_resp):
        results = doaj.search("open access")

    assert len(results) == 1
    r = results[0]
    assert r.title == "Open Access Study"
    assert r.authors == ["Rosa Park"]
    assert r.year == 2022
    assert r.doi == "10.4/oa"
    assert r.source == "doaj"
    assert r.oa_pdf_url == "https://example.org/oa.pdf"


def test_search_raises_source_error_on_request_exception():
    with patch.object(
        doaj.requests, "get", side_effect=requests.RequestException("timeout")
    ):
        try:
            doaj.search("x")
        except SourceError as e:
            assert e.source == "doaj"
        else:
            raise AssertionError("expected SourceError")


def test_search_handles_missing_optional_fields():
    mock_resp = Mock()
    mock_resp.json.return_value = {"results": [{"bibjson": {}}]}
    mock_resp.raise_for_status.return_value = None
    with patch.object(doaj.requests, "get", return_value=mock_resp):
        results = doaj.search("x")
    assert results[0].title == ""
    assert results[0].authors == []
    assert results[0].year is None
    assert results[0].doi is None
    assert results[0].oa_pdf_url is None


def test_search_skips_non_numeric_year():
    mock_resp = Mock()
    mock_resp.json.return_value = {
        "results": [{"bibjson": {"title": "Bad Year", "year": "not-a-year"}}]
    }
    mock_resp.raise_for_status.return_value = None
    with patch.object(doaj.requests, "get", return_value=mock_resp):
        results = doaj.search("x")
    assert results[0].title == "Bad Year"
    assert results[0].year is None
