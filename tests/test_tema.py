from fastapi.testclient import TestClient

from ricerca import config as config_module
from ricerca.app import app
from ricerca.config import Config

client = TestClient(app)


def test_di_partenza_segue_il_sistema():
    assert 'data-tema="auto"' in client.get("/").text


def test_la_scelta_del_tema_resta():
    client.post("/tema/scuro")
    assert config_module.load().tema == "scuro"
    assert 'data-tema="scuro"' in client.get("/").text

    client.post("/tema/chiaro")
    assert 'data-tema="chiaro"' in client.get("/").text


def test_un_tema_inventato_ricade_su_auto():
    client.post("/tema/fucsia")
    assert config_module.load().tema == "auto"


def test_il_bottone_scelto_e_evidenziato():
    pagina = client.post("/tema/scuro").text
    assert 'class="lingua attiva"' in pagina
    assert "dark" in pagina


def test_le_impostazioni_non_azzerano_il_tema():
    client.post("/tema/scuro")
    client.post("/impostazioni", data={
        "mailto": "x@y.it", "llm_base_url": "", "llm_model": "", "llm_api_key": "",
        "core_api_key": "", "s2_api_key": "", "ncbi_api_key": "",
        "zotero_api_key": "", "zotero_library_id": "", "zotero_library_type": "users",
    })
    assert config_module.load().tema == "scuro"


def test_il_cambio_lingua_non_azzera_il_tema():
    client.post("/tema/chiaro")
    client.post("/lingua/it")
    assert config_module.load().tema == "chiaro"
    assert config_module.load().lang == "it"
