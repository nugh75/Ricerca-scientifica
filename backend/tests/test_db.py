from litreview import config
from litreview import db as db_module


def test_get_connection_creates_all_tables(tmp_db_path):
    conn = db_module.get_connection(tmp_db_path)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"articles", "chat_sessions", "settings"} <= tables
    conn.close()


def test_get_connection_creates_parent_dir(tmp_path):
    nested = tmp_path / "nested" / "dir" / "lib.db"
    conn = db_module.get_connection(nested)
    assert nested.exists()
    conn.close()


def test_get_db_yields_working_connection_and_closes(tmp_db_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_db_path)
    gen = db_module.get_db()
    conn = next(gen)
    conn.execute("SELECT 1")
    try:
        next(gen)
    except StopIteration:
        pass
    else:
        raise AssertionError("generator should stop after one yield")
