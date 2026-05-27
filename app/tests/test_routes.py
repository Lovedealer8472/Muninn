"""Tests for key HTTP routes."""

def test_login_page(client):
    rv = client.get("/login")
    assert rv.status_code == 200


def test_board_requires_login(client):
    rv = client.get("/")
    assert rv.status_code == 302
    assert "/login" in rv.headers["Location"]


def test_track_public(client):
    rv = client.get("/track")
    assert rv.status_code == 200


def test_board_after_login(logged_in_client):
    rv = logged_in_client.get("/")
    assert rv.status_code == 200


def test_pwa_manifest_disabled(client):
    rv = client.get("/manifest.webmanifest")
    assert rv.status_code == 404
