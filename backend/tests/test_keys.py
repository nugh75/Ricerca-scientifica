import keyring.errors
import pytest

from litreview import keys


class FakeKeyringBackend:
    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}

    def set_password(self, service, name, value):
        self.store[(service, name)] = value

    def get_password(self, service, name):
        return self.store.get((service, name))

    def delete_password(self, service, name):
        if (service, name) not in self.store:
            raise keyring.errors.PasswordDeleteError("not found")
        del self.store[(service, name)]


@pytest.fixture
def fake_backend(monkeypatch):
    backend = FakeKeyringBackend()
    monkeypatch.setattr(keys.keyring, "set_password", backend.set_password)
    monkeypatch.setattr(keys.keyring, "get_password", backend.get_password)
    monkeypatch.setattr(keys.keyring, "delete_password", backend.delete_password)
    return backend


def test_set_and_get_key_roundtrip(fake_backend):
    keys.set_key("deepseek_api_key", "sk-test-123")
    assert keys.get_key("deepseek_api_key") == "sk-test-123"


def test_get_key_returns_none_when_missing(fake_backend):
    assert keys.get_key("deepseek_api_key") is None


def test_has_key_true_after_set(fake_backend):
    keys.set_key("openalex_mailto", "me@example.org")
    assert keys.has_key("openalex_mailto") is True


def test_has_key_false_when_missing(fake_backend):
    assert keys.has_key("openalex_mailto") is False


def test_delete_key_removes_value(fake_backend):
    keys.set_key("crossref_mailto", "me@example.org")
    keys.delete_key("crossref_mailto")
    assert keys.get_key("crossref_mailto") is None


def test_delete_key_missing_does_not_raise(fake_backend):
    keys.delete_key("crossref_mailto")  # no error even if never set


def test_unknown_key_name_raises_value_error(fake_backend):
    with pytest.raises(ValueError):
        keys.set_key("not_a_real_key", "x")
    with pytest.raises(ValueError):
        keys.get_key("not_a_real_key")


def test_set_key_wraps_no_keyring_error(monkeypatch):
    def raise_no_keyring(*args, **kwargs):
        raise keyring.errors.NoKeyringError("no backend")

    monkeypatch.setattr(keys.keyring, "set_password", raise_no_keyring)
    with pytest.raises(keys.KeyringUnavailableError):
        keys.set_key("deepseek_api_key", "sk-test")
