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
