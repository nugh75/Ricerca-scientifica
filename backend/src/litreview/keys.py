import keyring
import keyring.errors

from .config import KEYRING_SERVICE

KNOWN_KEYS = [
    "openalex_mailto",
    "semantic_scholar_key",
    "crossref_mailto",
    "deepseek_api_key",
]


class KeyringUnavailableError(Exception):
    pass


def _validate(name: str) -> None:
    if name not in KNOWN_KEYS:
        raise ValueError(f"unknown key name: {name}")


def set_key(name: str, value: str) -> None:
    _validate(name)
    try:
        keyring.set_password(KEYRING_SERVICE, name, value)
    except keyring.errors.NoKeyringError as e:
        raise KeyringUnavailableError(
            "Nessun keyring di sistema disponibile. Su Linux installa e avvia "
            "gnome-keyring o un servizio Secret Service compatibile."
        ) from e


def get_key(name: str) -> str | None:
    _validate(name)
    try:
        return keyring.get_password(KEYRING_SERVICE, name)
    except keyring.errors.NoKeyringError as e:
        raise KeyringUnavailableError(
            "Nessun keyring di sistema disponibile. Su Linux installa e avvia "
            "gnome-keyring o un servizio Secret Service compatibile."
        ) from e


def delete_key(name: str) -> None:
    _validate(name)
    try:
        keyring.delete_password(KEYRING_SERVICE, name)
    except keyring.errors.PasswordDeleteError:
        pass


def has_key(name: str) -> bool:
    return bool(get_key(name))
