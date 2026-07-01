import hashlib
import os
from typing import Optional

from flask import g, has_request_context, request

from app import config


def get_user_email() -> Optional[str]:
    """Resolve the current user's email.

    A reverse proxy's ``X-Forwarded-User`` header takes precedence (real
    per-request auth); otherwise fall back to the fixed ``USER_EMAIL`` env
    config for single-user deployments without such a proxy.
    """
    if has_request_context():
        raw = request.headers.get("X-Forwarded-User", "")
        value = raw.strip()
        if value:
            return value
    fixed = (config.USER_EMAIL or "").strip()
    return fixed if fixed else None


def resolve_db_path(email: str) -> str:
    digest = hashlib.sha256(email.encode()).hexdigest()
    return os.path.join(config.DATA_DIR, "users", digest, "session.db")


def get_db_path() -> str:
    if has_request_context() and hasattr(g, "db_path"):
        return g.db_path
    return config.DB_FILE
