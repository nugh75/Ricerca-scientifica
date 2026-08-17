import socket
import sys

import pytest

from litreview import config
from litreview.__main__ import (
    DOCS_URL,
    HOST,
    PORT,
    _open_browser,
    _port_in_use,
    _redirect_logs_if_frozen,
    main,
)


def test_port_in_use_true_when_bound():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.bind((HOST, 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        assert _port_in_use(HOST, port) is True


def test_port_in_use_false_when_free():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.bind((HOST, 0))
        port = srv.getsockname()[1]
    assert _port_in_use(HOST, port) is False


def test_open_browser_opens_docs_url(monkeypatch):
    opened = []
    monkeypatch.setattr("litreview.__main__.webbrowser.open", opened.append)
    _open_browser()
    assert opened == [DOCS_URL]


def test_main_returns_1_when_port_in_use(monkeypatch, capsys):
    monkeypatch.setattr("litreview.__main__._port_in_use", lambda h, p: True)
    monkeypatch.setattr(
        "litreview.__main__.uvicorn.run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("non deve partire"))
    )
    assert main() == 1
    err = capsys.readouterr().err
    assert "8756" in err
    assert "occupat" in err


def test_main_runs_uvicorn_without_browser_when_env_set(monkeypatch):
    monkeypatch.setenv("LITREVIEW_NO_BROWSER", "1")
    monkeypatch.setattr("litreview.__main__._port_in_use", lambda h, p: False)
    timers = []
    monkeypatch.setattr("litreview.__main__.threading.Timer", lambda *a: timers.append(a) or timers)
    kwargs = {}
    monkeypatch.setattr(
        "litreview.__main__.uvicorn.run", lambda app, **k: kwargs.update(k)
    )
    assert main() == 0
    assert kwargs == {"host": HOST, "port": PORT, "log_level": "info"}
    assert timers == []


def test_main_schedules_browser_timer_by_default(monkeypatch):
    monkeypatch.delenv("LITREVIEW_NO_BROWSER", raising=False)
    monkeypatch.setattr("litreview.__main__._port_in_use", lambda h, p: False)
    timers = []

    class FakeTimer:
        def __init__(self, *args):
            timers.append(args)

        def start(self):
            pass

    monkeypatch.setattr("litreview.__main__.threading.Timer", FakeTimer)
    monkeypatch.setattr("litreview.__main__.uvicorn.run", lambda *a, **k: None)
    assert main() == 0
    assert len(timers) == 1
    delay, target = timers[0]
    assert delay == 1.5
    assert target is _open_browser


def test_redirect_logs_when_frozen_and_not_tty(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "APP_DIR", tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    class NoTty:
        def isatty(self):
            return False

    monkeypatch.setattr(sys, "stdout", NoTty())
    monkeypatch.setattr(sys, "stderr", NoTty())
    _redirect_logs_if_frozen()
    assert sys.stdout.name == str(tmp_path / "server.log")
    assert sys.stderr is sys.stdout


def test_no_redirect_when_not_frozen(monkeypatch, tmp_path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(config, "APP_DIR", tmp_path)
    before = sys.stdout
    _redirect_logs_if_frozen()
    assert sys.stdout is before


def test_no_redirect_when_frozen_but_tty(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(config, "APP_DIR", tmp_path)

    class Tty:
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdout", Tty())
    before = sys.stdout
    _redirect_logs_if_frozen()
    assert sys.stdout is before
