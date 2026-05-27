"""Tests for trial expiry logic."""

from datetime import date, timedelta

import pytest

from muninn import trial as trial_mod


@pytest.fixture(autouse=True)
def clear_trial_env(monkeypatch):
    monkeypatch.delenv("TRIAL_EXPIRES_AT", raising=False)


def test_no_trial_when_unset():
    assert trial_mod.trial_active() is False
    assert trial_mod.trial_expired() is False
    assert trial_mod.trial_context()["trial_active"] is False


def test_trial_days_remaining(monkeypatch):
    future = (date.today() + timedelta(days=5)).isoformat()
    monkeypatch.setenv("TRIAL_EXPIRES_AT", future)
    assert trial_mod.trial_active() is True
    assert trial_mod.trial_days_remaining() == 5
    assert trial_mod.trial_expired() is False


def test_trial_expired(monkeypatch):
    past = (date.today() - timedelta(days=1)).isoformat()
    monkeypatch.setenv("TRIAL_EXPIRES_AT", past)
    assert trial_mod.trial_expired() is True
    assert trial_mod.trial_days_remaining() == 0


def test_trial_last_day_still_active(monkeypatch):
    today = date.today().isoformat()
    monkeypatch.setenv("TRIAL_EXPIRES_AT", today)
    assert trial_mod.trial_expired() is False
    assert trial_mod.trial_days_remaining() == 0
