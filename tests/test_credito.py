from fastapi.testclient import TestClient

from ricerca import costo
from ricerca import config as config_module
from ricerca.app import app
from ricerca.config import Config

client = TestClient(app)


def test_le_impostazioni_mostrano_quanto_resta():
    config_module.save(Config(configurato="1", openalex_api_key="k"))
    costo.aggiungi(0.25)
    pagina = client.get("/impostazioni").text
    assert "0.25" in pagina
    assert "0.75" in pagina


def test_senza_chiave_il_budget_e_quello_stretto():
    config_module.save(Config(configurato="1"))
    pagina = client.get("/impostazioni").text
    assert "0.10" in pagina
