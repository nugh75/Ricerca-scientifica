import pytest

from ricerca import config as config_module
from ricerca.config import Config
from ricerca.models import Block, Strategy


@pytest.fixture
def strategy():
    return Strategy(
        blocks=[
            Block("Concetto principale", ["AI literacy", "AI competence"]),
            Block("Popolazione", ["teacher", "educator"]),
        ],
        mesh=["Artificial Intelligence"],
    )


@pytest.fixture
def config():
    return Config(mailto="test@example.org")


@pytest.fixture(autouse=True)
def cache_spenta(monkeypatch):
    """La cache falserebbe i conteggi di chiamata dei test."""

    monkeypatch.setenv("RICERCA_CACHE", "0")


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Nessun test deve leggere o scrivere la configurazione reale."""

    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def esegui_ricerca():
    """La ricerca è un lavoro in background: qui la si attende.

    Restituisce la pagina finale, quella che l'utente vedrebbe a lavoro
    concluso.
    """

    import re
    import time

    def attendi(client, dati, tentativi: int = 200):
        risposta = client.post("/cerca", data=dati)
        trovato = re.search(r"/lavoro/([A-Za-z0-9_-]+)", risposta.text)
        assert trovato, f"nessun lavoro avviato: {risposta.text[:200]}"
        for _ in range(tentativi):
            pagina = client.get(f"/lavoro/{trovato.group(1)}")
            if "/lavoro/" not in pagina.text:
                return pagina
            time.sleep(0.02)
        raise AssertionError("il lavoro non si è concluso")

    return attendi


def avviso_di(risposta) -> str:
    """Il testo dell'avviso mandato alla pagina, dall'intestazione HX-Trigger."""

    import json

    intestazione = risposta.headers.get("HX-Trigger")
    if not intestazione:
        return ""
    return json.loads(intestazione).get("avviso", {}).get("testo", "")
