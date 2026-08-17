from unittest.mock import Mock, patch

import requests

from litreview.api_clients import openalex
from litreview.api_clients.base import SourceError

SAMPLE_RESPONSE = {
    "results": [
        {
            "title": "A Study of Something",
            "authorships": [
                {"author": {"display_name": "Jane Smith"}},
                {"author": {"display_name": "John Doe"}},
            ],
            "publication_year": 2021,
            "doi": "https://doi.org/10.1/abc",
            "open_access": {"oa_url": "https://example.org/paper.pdf"},
        }
    ]
}


def test_search_normalizes_results():
    mock_resp = Mock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status.return_value = None
    with patch.object(openalex.requests, "get", return_value=mock_resp) as mock_get:
        results = openalex.search("something", mailto="me@example.org")

    assert len(results) == 1
    r = results[0]
    assert r.title == "A Study of Something"
    assert r.authors == ["Jane Smith", "John Doe"]
    assert r.year == 2021
    assert r.doi == "https://doi.org/10.1/abc"
    assert r.source == "openalex"
    assert r.oa_pdf_url == "https://example.org/paper.pdf"

    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["mailto"] == "me@example.org"


def test_search_omits_mailto_when_not_given():
    mock_resp = Mock()
    mock_resp.json.return_value = {"results": []}
    mock_resp.raise_for_status.return_value = None
    with patch.object(openalex.requests, "get", return_value=mock_resp) as mock_get:
        openalex.search("something")
    assert "mailto" not in mock_get.call_args.kwargs["params"]


def test_search_raises_source_error_on_request_exception():
    with patch.object(
        openalex.requests, "get", side_effect=requests.RequestException("timeout")
    ):
        try:
            openalex.search("something")
        except SourceError as e:
            assert e.source == "openalex"
        else:
            raise AssertionError("expected SourceError")


def test_search_handles_missing_optional_fields():
    mock_resp = Mock()
    mock_resp.json.return_value = {"results": [{"title": "No extras"}]}
    mock_resp.raise_for_status.return_value = None
    with patch.object(openalex.requests, "get", return_value=mock_resp):
        results = openalex.search("x")
    assert results[0].authors == []
    assert results[0].year is None
    assert results[0].doi is None
    assert results[0].oa_pdf_url is None
