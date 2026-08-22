import socket

import pytest

from ricerca.cli import free_port, main


def test_free_port_salta_le_porte_occupate():
    with socket.socket() as occupata:
        occupata.bind(("127.0.0.1", 0))
        porta = occupata.getsockname()[1]
        occupata.listen()
        assert free_port(porta) == porta + 1


def test_free_port_senza_porte_libere_esce():
    with socket.socket() as occupata:
        occupata.bind(("127.0.0.1", 0))
        porta = occupata.getsockname()[1]
        occupata.listen()
        with pytest.raises(SystemExit):
            free_port(porta, attempts=1)


def test_senza_comando_stampa_aiuto(capsys):
    assert main([]) == 0
    assert "serve" in capsys.readouterr().out


def scelta_di_avvio(monkeypatch, argomenti, **impostazioni):
    """Che cosa passa `serve` a finestra.apri, senza avviare il server."""

    from ricerca import cli, config as config_module, finestra
    from ricerca.config import Config

    config_module.save(Config(configurato="1", **impostazioni))
    passati = {}

    class TimerFinto:
        def __init__(self, _ritardo, funzione, args=()):
            passati["funzione"] = funzione
            passati["args"] = args

        def start(self):
            pass

    monkeypatch.setattr(cli.threading, "Timer", TimerFinto)
    monkeypatch.setattr(cli.uvicorn, "run", lambda *a, **kw: None)
    assert main(argomenti) == 0
    assert passati["funzione"] is finestra.apri
    return passati["args"][1:]


def test_serve_segue_la_scelta_salvata_in_impostazioni(monkeypatch):
    assert scelta_di_avvio(monkeypatch, ["serve"]) == (True, "")
    assert scelta_di_avvio(monkeypatch, ["serve"], apertura="scheda") == (False, "")
    assert scelta_di_avvio(
        monkeypatch, ["serve"], browser="/usr/bin/vivaldi"
    ) == (True, "/usr/bin/vivaldi")


def test_le_opzioni_della_riga_di_comando_vincono_sulla_scelta_salvata(monkeypatch):
    assert scelta_di_avvio(monkeypatch, ["serve", "--scheda"]) == (False, "")
    assert scelta_di_avvio(
        monkeypatch, ["serve", "--browser", "predefinito"], browser="/usr/bin/vivaldi"
    ) == (True, "predefinito")
