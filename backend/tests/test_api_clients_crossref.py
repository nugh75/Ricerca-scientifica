from unittest.mock import Mock, patch

import requests

from litreview.api_clients import crossref
from litreview.api_clients.base import SourceError

SAMPLE_RESPONSE = {
    "message": {
        "items": [
            {
                "title": ["On Networks"],
                "author": [{"given": "Grace", "family": "Hopper"}],
                "issued": {"date-parts": [[2018, 5]]},
                "DOI": "10.3/net",
                "abstract": "<jats:p>About networks.</jats:p>",
            }
        ]
    }
}


def test_search_normalizes_results():
    mock_resp = Mock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status.return_value = None
    with patch.object(crossref.requests, "get", return_value=mock_resp) as mock_get:
        results = crossref.search("networks", mailto="me@example.org")

    assert len(results) == 1
    r = results[0]
    assert r.title == "On Networks"
    assert r.authors == ["Grace Hopper"]
    assert r.year == 2018
    assert r.doi == "10.3/net"
    assert r.source == "crossref"
    assert "me@example.org" in mock_get.call_args.kwargs["headers"]["User-Agent"]


def test_search_raises_source_error_on_request_exception():
    with patch.object(
        crossref.requests, "get", side_effect=requests.RequestException("down")
    ):
        try:
            crossref.search("x")
        except SourceError as e:
            assert e.source == "crossref"
        else:
            raise AssertionError("expected SourceError")


def test_search_handles_missing_optional_fields():
    mock_resp = Mock()
    mock_resp.json.return_value = {"message": {"items": [{}]}}
    mock_resp.raise_for_status.return_value = None
    with patch.object(crossref.requests, "get", return_value=mock_resp):
        results = crossref.search("x")
    assert results[0].title == ""
    assert results[0].authors == []
    assert results[0].year is None
    assert results[0].doi is None
