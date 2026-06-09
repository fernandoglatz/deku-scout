import logging

from flask import Flask

from app.db import init_config_table

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")

    # Initialize config table on startup
    init_config_table()

    from app.web import web_bp
    app.register_blueprint(web_bp)

    return app
