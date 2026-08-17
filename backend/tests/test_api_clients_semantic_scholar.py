from unittest.mock import Mock, patch

import requests

from litreview.api_clients import semantic_scholar
from litreview.api_clients.base import SourceError

SAMPLE_RESPONSE = {
    "data": [
        {
            "title": "Deep Learning Basics",
            "authors": [{"name": "Ada Lovelace"}, {"name": "Alan Turing"}],
            "year": 2019,
            "externalIds": {"DOI": "10.2/xyz"},
            "abstract": "An intro to deep learning.",
            "openAccessPdf": {"url": "https://example.org/dl.pdf"},
        }
    ]
}


def test_search_normalizes_results():
    mock_resp = Mock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status.return_value = None
    with patch.object(
        semantic_scholar.requests, "get", return_value=mock_resp
    ) as mock_get:
        results = semantic_scholar.search("deep learning", api_key="ss-key")

    assert len(results) == 1
    r = results[0]
    assert r.title == "Deep Learning Basics"
    assert r.authors == ["Ada Lovelace", "Alan Turing"]
    assert r.year == 2019
    assert r.doi == "10.2/xyz"
    assert r.source == "semantic_scholar"
    assert r.abstract == "An intro to deep learning."
    assert r.oa_pdf_url == "https://example.org/dl.pdf"
    assert mock_get.call_args.kwargs["headers"]["x-api-key"] == "ss-key"


def test_search_without_api_key_sends_no_header():
    mock_resp = Mock()
    mock_resp.json.return_value = {"data": []}
    mock_resp.raise_for_status.return_value = None
    with patch.object(semantic_scholar.requests, "get", return_value=mock_resp) as mock_get:
        semantic_scholar.search("x")
    assert mock_get.call_args.kwargs["headers"] == {}


def test_search_raises_source_error_on_request_exception():
    with patch.object(
        semantic_scholar.requests, "get", side_effect=requests.RequestException("boom")
    ):
        try:
            semantic_scholar.search("x")
        except SourceError as e:
            assert e.source == "semantic_scholar"
        else:
            raise AssertionError("expected SourceError")


def test_search_handles_missing_optional_fields():
    mock_resp = Mock()
    mock_resp.json.return_value = {"data": [{"title": "Bare"}]}
    mock_resp.raise_for_status.return_value = None
    with patch.object(semantic_scholar.requests, "get", return_value=mock_resp):
        results = semantic_scholar.search("x")
    assert results[0].authors == []
    assert results[0].doi is None
    assert results[0].oa_pdf_url is None
