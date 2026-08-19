from fastapi.testclient import TestClient

from ricerca import config as config_module
from ricerca import macchina
from ricerca.app import app
from ricerca.config import Config

client = TestClient(app)


def test_al_primo_avvio_si_arriva_alla_configurazione():
    risposta = client.get("/", follow_redirects=False)
    assert risposta.status_code == 303
    assert risposta.headers["location"] == "/benvenuto"


def test_dopo_la_configurazione_si_va_dritti_all_app():
    config_module.save(Config(configurato="1"))
    assert client.get("/", follow_redirects=False).status_code == 200


def test_la_guida_spiega_ogni_voce():
    pagina = client.get("/benvenuto").text
    for pezzo in ("Courtesy email", "Language model", "Database keys",
                  "ollama pull", "DeepSeek", "OpenAI", "Semantic Scholar", "Zotero"):
        assert pezzo in pagina, pezzo
    assert "nothing leaves your computer" in pagina   # la nota sulla riservatezza


def test_la_guida_consiglia_modelli_per_questa_macchina():
    pagina = client.get("/benvenuto").text
    for modello in macchina.consiglio():
        assert f"ollama pull {modello.nome}" in pagina
        assert modello.peso in pagina


def test_salvare_dalla_guida_configura_e_apre_l_app():
    risposta = client.post("/benvenuto", data={
        "mailto": "x@y.it", "llm_base_url": "http://localhost:11434/v1",
        "llm_model": "qwen3:8b", "llm_api_key": "", "core_api_key": "chiave-core",
        "s2_api_key": "", "ncbi_api_key": "", "zotero_api_key": "", "zotero_library_id": "",
        "lingua": "it", "tema": "scuro",
    }, follow_redirects=False)

    assert risposta.status_code == 303 and risposta.headers["location"] == "/"
    config = config_module.load()
    assert config.configurato == "1"
    assert config.mailto == "x@y.it"
    assert config.llm_model == "qwen3:8b"
    assert config.core_api_key == "chiave-core"
    assert config.lang == "it" and config.tema == "scuro"


def test_saltare_la_guida_non_chiede_nulla():
    risposta = client.post("/salta-benvenuto", follow_redirects=False)
    assert risposta.status_code == 303
    assert config_module.load().configurato == "1"
    assert config_module.load().mailto == ""


def test_la_guida_si_puo_rivedere_dalle_impostazioni():
    config_module.save(Config(configurato="1"))
    assert 'href="/benvenuto"' in client.get("/impostazioni").text


def test_i_consigli_seguono_la_memoria_disponibile():
    poca = [m.nome for m in macchina.consiglio(memoria=6, silicio_apple=False)]
    media = [m.nome for m in macchina.consiglio(memoria=24, silicio_apple=False)]
    tanta_mac = [m.nome for m in macchina.consiglio(memoria=64, silicio_apple=True)]

    assert poca == ["qwen3:1.7b", "llama3.2:3b"]
    assert media[0] == "qwen3:8b"
    assert "qwen3:30b-a3b" in tanta_mac          # sui Mac Apple Silicon
    assert "gpt-oss:20b" in [m.nome for m in macchina.consiglio(memoria=64, silicio_apple=False)]


def test_senza_dati_sulla_memoria_si_resta_prudenti():
    assert [m.nome for m in macchina.consiglio(memoria=None, silicio_apple=False)] == ["qwen3:4b"]


def test_una_chiave_lasciata_vuota_non_cancella_quella_salvata():
    config_module.save(Config(core_api_key="vecchia"))
    client.post("/benvenuto", data={"mailto": "", "llm_base_url": "", "llm_model": "",
                                    "llm_api_key": "", "core_api_key": "", "s2_api_key": "",
                                    "ncbi_api_key": "", "zotero_api_key": "",
                                    "zotero_library_id": "", "lingua": "en", "tema": "auto"})
    assert config_module.load().core_api_key == "vecchia"


def test_i_motivi_dei_modelli_seguono_la_lingua():
    """Vale qualunque sia la memoria della macchina che esegue il test."""

    import html

    from ricerca import i18n

    inglese = html.unescape(client.get("/benvenuto").text)
    for modello in macchina.consiglio():
        assert i18n.STRINGS["en"][modello.motivo] in inglese

    config_module.save(Config(lang="it"))
    italiano = html.unescape(client.get("/benvenuto").text)
    for modello in macchina.consiglio():
        assert i18n.STRINGS["it"][modello.motivo] in italiano


def test_la_guida_e_raggiungibile_anche_dopo_la_prima_volta():
    config_module.save(Config(configurato="1"))
    assert client.get("/benvenuto").status_code == 200
