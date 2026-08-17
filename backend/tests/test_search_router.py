from litreview import keys
from litreview.api_clients import crossref, doaj, openalex, semantic_scholar
from litreview.api_clients.base import NormalizedResult, SourceError


def test_search_merges_results_from_multiple_sources(client, monkeypatch):
    monkeypatch.setattr(
        openalex,
        "search",
        lambda q, mailto=None, per_page=10: [
            NormalizedResult(
                title="Paper A", authors=["Smith J"], year=2020,
                doi="10.1/a", source="openalex",
            )
        ],
    )
    monkeypatch.setattr(
        semantic_scholar, "search", lambda q, api_key=None, per_page=10: []
    )
    monkeypatch.setattr(crossref, "search", lambda q, mailto=None, per_page=10: [])
    monkeypatch.setattr(doaj, "search", lambda q, per_page=10: [])

    resp = client.post(
        "/search",
        json={"query": "test", "sources": ["openalex", "semantic_scholar", "crossref", "doaj"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["title"] == "Paper A"
    assert data["errors"] == {}


def test_search_reports_per_source_errors_without_failing_whole_request(client, monkeypatch):
    monkeypatch.setattr(openalex, "search", lambda q, mailto=None, per_page=10: [])
    monkeypatch.setattr(
        semantic_scholar,
        "search",
        lambda q, api_key=None, per_page=10: (_ for _ in ()).throw(
            SourceError("semantic_scholar", "timeout")
        ),
    )
    monkeypatch.setattr(crossref, "search", lambda q, mailto=None, per_page=10: [])
    monkeypatch.setattr(doaj, "search", lambda q, per_page=10: [])

    resp = client.post(
        "/search",
        json={"query": "test", "sources": ["openalex", "semantic_scholar", "crossref", "doaj"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"] == []
    assert data["errors"] == {"semantic_scholar": "timeout"}


def test_search_only_queries_requested_sources(client, monkeypatch):
    called = []
    monkeypatch.setattr(
        openalex,
        "search",
        lambda q, mailto=None, per_page=10: called.append("openalex") or [],
    )
    monkeypatch.setattr(
        semantic_scholar,
        "search",
        lambda q, api_key=None, per_page=10: called.append("semantic_scholar") or [],
    )
    resp = client.post("/search", json={"query": "test", "sources": ["openalex"]})
    assert resp.status_code == 200
    assert called == ["openalex"]


def test_search_treats_keyring_unavailable_as_no_key(client, monkeypatch):
    def raise_unavailable(name):
        raise keys.KeyringUnavailableError("no backend")

    monkeypatch.setattr(keys, "get_key", raise_unavailable)

    received = {}

    def fake_openalex_search(q, mailto=None, per_page=10):
        received["mailto"] = mailto
        return []

    monkeypatch.setattr(openalex, "search", fake_openalex_search)
    monkeypatch.setattr(semantic_scholar, "search", lambda q, api_key=None, per_page=10: [])
    monkeypatch.setattr(crossref, "search", lambda q, mailto=None, per_page=10: [])
    monkeypatch.setattr(doaj, "search", lambda q, per_page=10: [])

    resp = client.post("/search", json={"query": "test", "sources": ["openalex"]})
    assert resp.status_code == 200
    assert received["mailto"] is None
