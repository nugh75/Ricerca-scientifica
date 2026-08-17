import pytest


@pytest.fixture
def tmp_db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def conn(tmp_db_path):
    from litreview import db as db_module

    connection = db_module.get_connection(tmp_db_path)
    yield connection
    connection.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from litreview import db as db_module
    from litreview.main import app

    test_db_path = tmp_path / "test.db"

    def override_get_db():
        conn = db_module.get_connection(test_db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[db_module.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
