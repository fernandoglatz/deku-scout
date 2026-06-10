import hashlib
import os

import pytest
from flask import Flask, g


def test_resolve_db_path_is_deterministic():
    from app.user import resolve_db_path
    assert resolve_db_path("user@example.com") == resolve_db_path("user@example.com")


def test_resolve_db_path_uses_sha256():
    from app.user import resolve_db_path
    email = "user@example.com"
    expected_hash = hashlib.sha256(email.encode()).hexdigest()
    path = resolve_db_path(email)
    assert expected_hash in path
    assert path.endswith("session.db")


def test_resolve_db_path_different_emails_differ():
    from app.user import resolve_db_path
    assert resolve_db_path("a@example.com") != resolve_db_path("b@example.com")


def test_resolve_db_path_is_under_data_dir(monkeypatch, tmp_path):
    import app.config as config_module
    monkeypatch.setattr(config_module, "DATA_DIR", str(tmp_path))
    from app.user import resolve_db_path
    path = resolve_db_path("user@example.com")
    assert path.startswith(os.path.join(str(tmp_path), "users"))


def test_get_user_email_returns_none_outside_request():
    from app.user import get_user_email
    assert get_user_email() is None


def test_get_user_email_returns_email_from_header():
    from app.user import get_user_email
    app = Flask(__name__)
    with app.test_request_context(headers={"X-Forwarded-User": "alice@example.com"}):
        assert get_user_email() == "alice@example.com"


def test_get_user_email_strips_whitespace():
    from app.user import get_user_email
    app = Flask(__name__)
    with app.test_request_context(headers={"X-Forwarded-User": "  alice@example.com  "}):
        assert get_user_email() == "alice@example.com"


def test_get_user_email_returns_none_when_header_absent():
    from app.user import get_user_email
    app = Flask(__name__)
    with app.test_request_context():
        assert get_user_email() is None


def test_get_user_email_returns_none_when_header_blank():
    from app.user import get_user_email
    app = Flask(__name__)
    with app.test_request_context(headers={"X-Forwarded-User": "   "}):
        assert get_user_email() is None


def test_get_db_path_outside_request_returns_default():
    from app.user import get_db_path
    from app.config import DB_FILE
    assert get_db_path() == DB_FILE


def test_get_db_path_returns_g_db_path_in_request():
    from app.user import get_db_path
    app = Flask(__name__)
    with app.test_request_context():
        g.db_path = "/tmp/custom.db"
        assert get_db_path() == "/tmp/custom.db"
