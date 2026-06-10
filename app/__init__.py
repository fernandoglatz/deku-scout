import logging

from flask import Flask, g

from app import config
from app.migrations import run_migrations
from app.user import get_user_email, resolve_db_path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")

    initialized_dbs: set[str] = set()

    run_migrations(config.DB_FILE)
    initialized_dbs.add(config.DB_FILE)

    @app.before_request
    def _set_db_path():
        email = get_user_email()
        db_path = resolve_db_path(email) if email else config.DB_FILE
        g.db_path = db_path
        if db_path not in initialized_dbs:
            run_migrations(db_path)
            initialized_dbs.add(db_path)

    from app.web import web_bp
    app.register_blueprint(web_bp)

    return app
