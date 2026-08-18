import json
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from litreview import config
from litreview.__main__ import (
    DEFAULT_PORT,
    HOST,
    PORT_SCAN_LIMIT,
    _announce,
    _is_litreview,
    _open_browser,
    _port_in_use,
    _redirect_logs_if_frozen,
    _resolve_port,
    docs_url,
    main,
)


def _start_server(status, payload):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/health" or status != 200:
                self.send_error(404)
                return
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    srv = HTTPServer((HOST, 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture
def health_server():
    servers = []

    def start(status=200, payload=None):
        srv = _start_server(status, payload if payload is not None else {"app": "litreview"})
        servers.append(srv)
        return srv.server_address[1]

    yield start
    for srv in servers:
        srv.shutdown()
        srv.server_close()


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


def test_is_litreview_true_for_our_health_endpoint(health_server):
    port = health_server()
    assert _is_litreview(HOST, port) is True


def test_is_litreview_false_for_another_app(health_server):
    port = health_server(payload={"app": "something-else"})
    assert _is_litreview(HOST, port) is False


def test_is_litreview_false_when_no_health_route(health_server):
    port = health_server(status=404)
    assert _is_litreview(HOST, port) is False


def test_is_litreview_false_when_nothing_listens():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.bind((HOST, 0))
        port = srv.getsockname()[1]
    assert _is_litreview(HOST, port) is False


def _fake_scan(monkeypatch, occupied, ours=()):
    monkeypatch.setattr("litreview.__main__._port_in_use", lambda h, p: p in occupied)
    monkeypatch.setattr("litreview.__main__._is_litreview", lambda h, p: p in ours)


def test_resolve_port_takes_the_default_when_free(monkeypatch):
    _fake_scan(monkeypatch, occupied=())
    assert _resolve_port(HOST) == (DEFAULT_PORT, False)


def test_resolve_port_reuses_our_own_backend(monkeypatch):
    _fake_scan(monkeypatch, occupied={DEFAULT_PORT}, ours={DEFAULT_PORT})
    assert _resolve_port(HOST) == (DEFAULT_PORT, True)


def test_resolve_port_skips_a_foreign_process(monkeypatch):
    _fake_scan(monkeypatch, occupied={DEFAULT_PORT})
    assert _resolve_port(HOST) == (DEFAULT_PORT + 1, False)


def test_resolve_port_reuses_our_backend_found_after_a_foreign_process(monkeypatch):
    _fake_scan(monkeypatch, occupied={DEFAULT_PORT, DEFAULT_PORT + 1}, ours={DEFAULT_PORT + 1})
    assert _resolve_port(HOST) == (DEFAULT_PORT + 1, True)


def test_resolve_port_returns_none_when_every_scanned_port_is_foreign(monkeypatch):
    everything = set(range(DEFAULT_PORT, DEFAULT_PORT + PORT_SCAN_LIMIT))
    _fake_scan(monkeypatch, occupied=everything)
    assert _resolve_port(HOST) is None


def test_announce_prints_reused_before_port(capsys):
    _announce(8757, True)
    out = capsys.readouterr().out.splitlines()
    # the frontend reads REUSED first, so it is already known when PORT arrives
    assert out == ["LITREVIEW_REUSED=1", "LITREVIEW_PORT=8757"]


def test_announce_marks_a_fresh_server_as_not_reused(capsys):
    _announce(8756, False)
    assert capsys.readouterr().out.splitlines() == ["LITREVIEW_REUSED=0", "LITREVIEW_PORT=8756"]


def test_announce_survives_missing_stdout(monkeypatch):
    # windowed PyInstaller build (console=False): sys.stdout is None
    monkeypatch.setattr(sys, "stdout", None)
    _announce(8756, False)


def test_open_browser_opens_docs_url_for_the_given_port(monkeypatch):
    opened = []
    monkeypatch.setattr("litreview.__main__.webbrowser.open", opened.append)
    _open_browser(8757)
    assert opened == [docs_url(8757)]


def test_main_announces_the_port_before_redirecting_logs(monkeypatch):
    # the announcement must reach the real stdout: after the redirect it would
    # land in server.log and the desktop app would never learn the port
    calls = []
    monkeypatch.setattr("litreview.__main__._resolve_port", lambda h: (8756, False))
    monkeypatch.setattr("litreview.__main__._announce", lambda *a: calls.append("announce"))
    monkeypatch.setattr(
        "litreview.__main__._redirect_logs_if_frozen", lambda: calls.append("redirect")
    )
    monkeypatch.setenv("LITREVIEW_NO_BROWSER", "1")
    monkeypatch.setattr("litreview.__main__.uvicorn.run", lambda *a, **k: None)
    assert main() == 0
    assert calls == ["announce", "redirect"]


def test_main_returns_1_when_no_port_is_available(monkeypatch, capsys):
    monkeypatch.setattr("litreview.__main__._resolve_port", lambda h: None)
    monkeypatch.setattr(
        "litreview.__main__.uvicorn.run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("non deve partire"))
    )
    assert main() == 1
    err = capsys.readouterr().err
    assert "8756" in err
    assert "occupat" in err


def test_main_returns_1_when_no_port_available_and_std_streams_none(monkeypatch):
    # windowed PyInstaller build (console=False): sys.stdout/stderr are None
    monkeypatch.setattr("litreview.__main__._resolve_port", lambda h: None)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert main() == 1


def test_main_warns_to_server_log_when_frozen_without_streams(monkeypatch, tmp_path):
    # frozen + no streams: the port message must reach server.log, not vanish
    monkeypatch.setattr(config, "APP_DIR", tmp_path)
    monkeypatch.setattr("litreview.__main__._resolve_port", lambda h: None)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert main() == 1
    assert "Impossibile avviare il server" in (
        tmp_path / "server.log"
    ).read_text(encoding="utf-8")


def test_main_reuses_a_running_instance_without_starting_a_second_server(monkeypatch, capsys):
    monkeypatch.setattr("litreview.__main__._resolve_port", lambda h: (8756, True))
    monkeypatch.setattr(
        "litreview.__main__.uvicorn.run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("non deve partire"))
    )
    monkeypatch.delenv("LITREVIEW_NO_BROWSER", raising=False)
    opened = []
    monkeypatch.setattr("litreview.__main__.webbrowser.open", opened.append)
    assert main() == 0
    assert opened == [docs_url(8756)]
    assert "LITREVIEW_REUSED=1" in capsys.readouterr().out


def test_main_reuse_respects_no_browser(monkeypatch):
    monkeypatch.setattr("litreview.__main__._resolve_port", lambda h: (8756, True))
    monkeypatch.setattr("litreview.__main__.uvicorn.run", lambda *a, **k: None)
    monkeypatch.setenv("LITREVIEW_NO_BROWSER", "1")
    opened = []
    monkeypatch.setattr("litreview.__main__.webbrowser.open", opened.append)
    assert main() == 0
    assert opened == []


def test_main_runs_uvicorn_on_the_resolved_port(monkeypatch):
    monkeypatch.setenv("LITREVIEW_NO_BROWSER", "1")
    monkeypatch.setattr("litreview.__main__._resolve_port", lambda h: (8759, False))
    timers = []
    monkeypatch.setattr("litreview.__main__.threading.Timer", lambda *a: timers.append(a) or timers)
    kwargs = {}
    monkeypatch.setattr(
        "litreview.__main__.uvicorn.run", lambda app, **k: kwargs.update(k)
    )
    assert main() == 0
    assert kwargs == {"host": HOST, "port": 8759, "log_level": "info"}
    assert timers == []


def test_main_schedules_browser_timer_for_the_resolved_port(monkeypatch):
    monkeypatch.delenv("LITREVIEW_NO_BROWSER", raising=False)
    monkeypatch.setattr("litreview.__main__._resolve_port", lambda h: (8757, False))
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
    delay, target, args = timers[0]
    assert delay == 1.5
    assert target is _open_browser
    assert args == (8757,)


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
