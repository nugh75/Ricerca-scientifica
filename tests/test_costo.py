from ricerca import costo
from ricerca.config import Config


def test_le_spese_si_sommano_nel_giorno():
    costo.aggiungi(0.001, "2026-08-20")
    costo.aggiungi(0.0001, "2026-08-20")
    assert costo.speso("2026-08-20") == 0.0011


def test_i_giorni_restano_separati():
    costo.aggiungi(0.5, "2026-08-19")
    costo.aggiungi(0.25, "2026-08-20")
    assert costo.speso("2026-08-19") == 0.5
    assert costo.speso("2026-08-20") == 0.25


def test_una_spesa_nulla_non_scrive_nulla():
    costo.aggiungi(0.0, "2026-08-20")
    assert costo.speso("2026-08-20") == 0.0


def test_il_budget_dipende_dalla_chiave():
    assert costo.budget(Config()) == 0.10
    assert costo.budget(Config(openalex_api_key="k")) == 1.00


def test_quanto_resta_non_va_sotto_zero():
    costo.aggiungi(0.4, costo.oggi())
    assert costo.resta(Config()) == 0.0
    assert costo.resta(Config(openalex_api_key="k")) == 0.6


def test_un_file_illeggibile_non_ferma_il_programma(isolated_config):
    (isolated_config / "openalex-costo.json").write_text("{rotto", encoding="utf-8")
    assert costo.speso("2026-08-20") == 0.0
    assert costo.aggiungi(0.001, "2026-08-20") == 0.001
