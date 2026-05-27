"""Pytest configuration for Muninn."""

import os
import tempfile

import pytest

from muninn import create_app
from muninn.db import init_db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    os.environ["PWA_ENABLED"] = "0"

    application = create_app(
        test_config={
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": db_path,
        }
    )
    application.config["WTF_CSRF_ENABLED"] = False

    import muninn.db as db_module
    db_module.DATABASE = db_path

    with application.app_context():
        init_db()

    yield application

    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_client(client):
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["role"] = "stjori"
        sess["user"] = "Stjóri"
    return client
