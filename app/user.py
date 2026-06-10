import hashlib
import os
from typing import Optional

from flask import g, has_request_context, request

from app import config


def get_user_email() -> Optional[str]:
    if not has_request_context():
        return None
    raw = request.headers.get("X-Forwarded-User", "")
    value = raw.strip()
    return value if value else None


def resolve_db_path(email: str) -> str:
    digest = hashlib.sha256(email.encode()).hexdigest()
    return os.path.join(config.DATA_DIR, "users", digest, "session.db")


def get_db_path() -> str:
    if has_request_context() and hasattr(g, "db_path"):
        return g.db_path
    return config.DB_FILE
