import stat

from ricerca import config as config_module
from ricerca.config import Config


def test_load_senza_file_restituisce_configurazione_vuota():
    assert config_module.load().llm_enabled is False


def test_save_e_load_conservano_i_valori_e_i_permessi(isolated_config):
    path = config_module.save(Config(mailto='a"b@x.it', llm_base_url="http://x/v1", llm_model="m"))
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    loaded = config_module.load()
    assert loaded.mailto == 'a"b@x.it'
    assert loaded.llm_enabled is True


def test_load_ignora_chiavi_sconosciute(isolated_config):
    (isolated_config / "config.toml").write_text('mailto = "x@y.it"\nsconosciuto = "1"\n')
    assert config_module.load().mailto == "x@y.it"
