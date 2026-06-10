import os
import tempfile

import pytest

from app import create_app


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Flask test client fixture."""
    import app.config as config_module

    db_path = str(tmp_path / "test_client.db")
    monkeypatch.setattr(config_module, "DB_FILE", db_path)

    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_db(monkeypatch):
    """Temporary database that patches app.db.DB_FILE."""
    import app.db as db_module
    from app.migrations import run_migrations

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(db_module, "DB_FILE", path)
    run_migrations(path)

    yield path

    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def temp_db_web(monkeypatch, tmp_path):
    """Temporary database that patches both app.db.DB_FILE and app.web.DB_FILE."""
    import app.db as db_module
    import app.web as web_module
    from app.migrations import run_migrations

    db_path = str(tmp_path / "test_web.db")
    monkeypatch.setattr(db_module, "DB_FILE", db_path)
    monkeypatch.setattr(web_module, "DB_FILE", db_path)
    run_migrations(db_path)

    yield db_path
