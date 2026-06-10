import logging

from flask import Flask

from app import config
from app.migrations import run_migrations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_initialized_dbs: set[str] = set()


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")

    run_migrations(config.DB_FILE)
    _initialized_dbs.add(config.DB_FILE)

    from app.user import get_user_email, resolve_db_path

    @app.before_request
    def _set_db_path():
        from flask import g
        email = get_user_email()
        db_path = resolve_db_path(email) if email else config.DB_FILE
        g.db_path = db_path
        if db_path not in _initialized_dbs:
            run_migrations(db_path)
            _initialized_dbs.add(db_path)

    from app.web import web_bp
    app.register_blueprint(web_bp)

    return app
