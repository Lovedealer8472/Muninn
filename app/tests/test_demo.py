"""Public demo mode (DEMO_MODE)."""

import os

import pytest

from muninn import demo as demo_mod


@pytest.fixture(autouse=True)
def clear_demo_env(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)


def test_demo_inactive_by_default():
    assert demo_mod.demo_active() is False
    assert demo_mod.demo_context()["demo_active"] is False


def test_demo_active(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    assert demo_mod.demo_active() is True
    assert demo_mod.demo_context()["demo_active"] is True
