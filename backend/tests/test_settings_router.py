from litreview import keys


def test_list_keys_reports_all_known_keys_as_unset(client, monkeypatch):
    monkeypatch.setattr(keys, "has_key", lambda name: False)
    resp = client.get("/settings/keys")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == set(keys.KNOWN_KEYS)
    assert all(v is False for v in data.values())


def test_list_keys_keyring_unavailable_returns_503(client, monkeypatch):
    def raise_unavailable(name):
        raise keys.KeyringUnavailableError("no backend")

    monkeypatch.setattr(keys, "has_key", raise_unavailable)
    resp = client.get("/settings/keys")
    assert resp.status_code == 503


def test_set_key_calls_keys_set_key(client, monkeypatch):
    calls = {}
    monkeypatch.setattr(keys, "set_key", lambda name, value: calls.setdefault(name, value))
    resp = client.put("/settings/keys/deepseek_api_key", json={"value": "sk-abc"})
    assert resp.status_code == 200
    assert calls["deepseek_api_key"] == "sk-abc"


def test_set_key_unknown_name_returns_404(client):
    resp = client.put("/settings/keys/not_real", json={"value": "x"})
    assert resp.status_code == 404


def test_set_key_keyring_unavailable_returns_503(client, monkeypatch):
    def raise_unavailable(name, value):
        raise keys.KeyringUnavailableError("no backend")

    monkeypatch.setattr(keys, "set_key", raise_unavailable)
    resp = client.put("/settings/keys/deepseek_api_key", json={"value": "sk-abc"})
    assert resp.status_code == 503


def test_delete_key_calls_keys_delete_key(client, monkeypatch):
    calls = []
    monkeypatch.setattr(keys, "delete_key", lambda name: calls.append(name))
    resp = client.delete("/settings/keys/deepseek_api_key")
    assert resp.status_code == 200
    assert calls == ["deepseek_api_key"]


def test_delete_key_unknown_name_returns_404(client):
    resp = client.delete("/settings/keys/not_real")
    assert resp.status_code == 404


def test_delete_key_keyring_unavailable_returns_503(client, monkeypatch):
    def raise_unavailable(name):
        raise keys.KeyringUnavailableError("no backend")

    monkeypatch.setattr(keys, "delete_key", raise_unavailable)
    resp = client.delete("/settings/keys/deepseek_api_key")
    assert resp.status_code == 503


def test_test_connection_unknown_key_returns_404(client):
    resp = client.post("/settings/keys/not_real/test", json={"value": "x"})
    assert resp.status_code == 404


def test_test_connection_openalex_success(client, monkeypatch):
    from litreview.api_clients import openalex

    monkeypatch.setattr(openalex, "search", lambda q, mailto=None, per_page=1: [])
    resp = client.post("/settings/keys/openalex_mailto/test", json={"value": "me@example.org"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


def test_test_connection_reports_source_error(client, monkeypatch):
    from litreview.api_clients import openalex
    from litreview.api_clients.base import SourceError

    def raise_error(q, mailto=None, per_page=1):
        raise SourceError("openalex", "bad request")

    monkeypatch.setattr(openalex, "search", raise_error)
    resp = client.post("/settings/keys/openalex_mailto/test", json={"value": "bad"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["message"] == "bad request"


def test_test_connection_semantic_scholar_success(client, monkeypatch):
    from litreview.api_clients import semantic_scholar

    monkeypatch.setattr(semantic_scholar, "search", lambda q, api_key=None, per_page=1: [])
    resp = client.post("/settings/keys/semantic_scholar_key/test", json={"value": "ss-key"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_test_connection_crossref_success(client, monkeypatch):
    from litreview.api_clients import crossref

    monkeypatch.setattr(crossref, "search", lambda q, mailto=None, per_page=1: [])
    resp = client.post("/settings/keys/crossref_mailto/test", json={"value": "me@example.org"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_test_connection_deepseek_success(client, monkeypatch):
    from litreview.routers import settings_router

    class FakeDeepSeek:
        def __init__(self, api_key):
            self.api_key = api_key

        def analyze(self, mode, text, **kwargs):
            return "ok"

    monkeypatch.setattr(settings_router, "DeepSeekClient", FakeDeepSeek)
    resp = client.post("/settings/keys/deepseek_api_key/test", json={"value": "sk-test"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_test_connection_deepseek_reports_failure(client, monkeypatch):
    from litreview.routers import settings_router

    class FailingDeepSeek:
        def __init__(self, api_key):
            pass

        def analyze(self, mode, text, **kwargs):
            raise RuntimeError("invalid api key")

    monkeypatch.setattr(settings_router, "DeepSeekClient", FailingDeepSeek)
    resp = client.post("/settings/keys/deepseek_api_key/test", json={"value": "sk-bad"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "invalid api key" in data["message"]
