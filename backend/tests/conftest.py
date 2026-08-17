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
