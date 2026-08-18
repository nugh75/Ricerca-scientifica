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
def isolated_config(tmp_path, monkeypatch):
    """Nessun test deve leggere o scrivere la configurazione reale."""

    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    return tmp_path
