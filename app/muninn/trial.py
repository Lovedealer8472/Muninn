"""Optional time-limited trial (TRIAL_EXPIRES_AT in .env)."""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Optional

from flask import render_template


def trial_expires_on() -> Optional[date]:
    raw = os.environ.get("TRIAL_EXPIRES_AT", "").strip()
    if not raw:
        return None
    try:
        if "T" in raw:
            return datetime.fromisoformat(raw).date()
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def trial_active() -> bool:
    return trial_expires_on() is not None


def trial_expired() -> bool:
    expires = trial_expires_on()
    if expires is None:
        return False
    return date.today() > expires


def trial_days_remaining() -> Optional[int]:
    expires = trial_expires_on()
    if expires is None:
        return None
    return max(0, (expires - date.today()).days)


def trial_context() -> dict:
    expires = trial_expires_on()
    if expires is None:
        return {
            "trial_active": False,
            "trial_expired": False,
            "trial_days_remaining": None,
            "trial_expires_on": None,
        }
    remaining = trial_days_remaining()
    return {
        "trial_active": True,
        "trial_expired": trial_expired(),
        "trial_days_remaining": remaining,
        "trial_expires_on": expires.isoformat(),
    }


def trial_expired_response():
    """Full-page response when trial period has ended."""
    expires = trial_expires_on()
    return (
        render_template(
            "trial_expired.html",
            trial_expires_on=expires.isoformat() if expires else "",
        ),
        403,
    )
