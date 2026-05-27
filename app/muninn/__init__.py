"""Muninn Flask application factory."""

import os

from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

from muninn.auth import inject_role_context
from muninn.config import MAX_UPLOAD_BYTES, upload_root_for
from muninn.db import bootstrap_database, init_app as init_db_app, init_db
from muninn.logging_config import configure_logging
from muninn.routes import register_routes
from muninn.services import email as email_service
from muninn.services import orders as orders_service
from muninn.trial import trial_context, trial_expired, trial_expired_response


APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def create_app(test_config: dict | None = None):
    load_dotenv()
    configure_logging()

    from flask import Flask, jsonify

    app = Flask(
        __name__,
        root_path=APP_ROOT,
        template_folder="templates",
        static_folder="static",
    )
    app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me")

    if test_config:
        app.config.update(test_config)

    if os.environ.get("BEHIND_PROXY", "1").lower() in ("1", "true", "yes", "on"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    init_db_app(app)
    orders_service.init_app(app)
    email_service.init_app(app)

    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    os.makedirs(upload_root_for(app), exist_ok=True)

    app.context_processor(inject_role_context)
    app.context_processor(trial_context)
    register_routes(app)

    @app.before_request
    def _enforce_trial():
        if app.config.get("TESTING") or not trial_expired():
            return None
        from flask import request

        if request.endpoint == "static":
            return None
        return trial_expired_response()

    @app.errorhandler(413)
    def too_large(_e):
        return jsonify({"error": "Skrá er of stór, hámark 25 MB."}), 413

    @app.cli.command("init-db")
    def init_db_command():
        """Create the database tables."""
        with app.app_context():
            init_db()
        print("Database initialized.")

    if not app.config.get("TESTING"):
        bootstrap_database()

    import logging
    from flask import request

    req_log = logging.getLogger("muninn.request")

    @app.before_request
    def _log_request_start():
        if req_log.isEnabledFor(logging.DEBUG):
            req_log.debug("%s %s", request.method, request.path)

    @app.after_request
    def _log_request_end(response):
        if req_log.isEnabledFor(logging.DEBUG):
            req_log.debug(
                "%s %s -> %s", request.method, request.path, response.status_code
            )
        return response

    return app
