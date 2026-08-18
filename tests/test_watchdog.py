import asyncio

import pytest
from fastapi.testclient import TestClient

from ricerca import watchdog
from ricerca.app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def stato_pulito():
    watchdog.stato = watchdog.Sorveglianza()
    return watchdog.stato


def test_senza_pagine_viste_non_si_ferma_mai(stato_pulito):
    lontano = stato_pulito.ultimo_battito + 10_000
    assert stato_pulito.deve_fermarsi(lontano) is False


def test_dopo_un_battito_il_silenzio_prolungato_ferma_il_server(stato_pulito):
    stato_pulito.battito()
    adesso = stato_pulito.ultimo_battito
    assert stato_pulito.deve_fermarsi(adesso + 5) is False
    assert stato_pulito.deve_fermarsi(adesso + watchdog.SILENZIO_MASSIMO + 1) is True


def test_la_pagina_chiusa_ferma_il_server_dopo_la_pausa(stato_pulito):
    stato_pulito.battito()
    stato_pulito.pagina_chiusa()
    adesso = stato_pulito.scadenza - 1
    assert stato_pulito.deve_fermarsi(adesso) is False
    assert stato_pulito.deve_fermarsi(stato_pulito.scadenza) is True


def test_un_nuovo_battito_annulla_lo_spegnimento(stato_pulito):
    stato_pulito.battito()
    stato_pulito.pagina_chiusa()
    stato_pulito.battito()  # la pagina e' stata solo ricaricata
    assert stato_pulito.scadenza is None
    assert stato_pulito.deve_fermarsi() is False


def test_le_rotte_battito_e_chiudi_rispondono():
    assert client.post("/battito").status_code == 204
    assert watchdog.stato.mai_vista_una_pagina is False
    assert client.post("/chiudi").status_code == 204
    assert watchdog.stato.scadenza is not None


def test_la_sorveglianza_e_spenta_se_non_richiesta(monkeypatch):
    monkeypatch.delenv(watchdog.VARIABILE, raising=False)
    assert watchdog.attiva() is False
    monkeypatch.setenv(watchdog.VARIABILE, "1")
    assert watchdog.attiva() is True


async def test_la_sorveglianza_chiama_lo_stop(monkeypatch, stato_pulito):
    monkeypatch.setattr(watchdog, "INTERVALLO_CONTROLLO", 0.01)
    fermato = []
    stato_pulito.battito()
    stato_pulito.scadenza = 0  # gia' scaduta
    await asyncio.wait_for(watchdog.sorveglia(ferma=lambda: fermato.append(True)), timeout=2)
    assert fermato == [True]
