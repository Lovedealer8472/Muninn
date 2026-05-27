"""Authentication helpers and decorators."""

import os
from functools import wraps

from flask import flash, redirect, session, url_for
from werkzeug.security import check_password_hash

from muninn.config import (
    ROLE_LABELS,
    ROLE_NOTANDI,
    ROLE_STJORI,
    password_default_hashes,
)

_STJORI_DEFAULT_HASH, _NOTANDI_DEFAULT_HASH = password_default_hashes()


def password_hash_for_role(role: str) -> str:
    """Stjóri: admin. Notandi: user. Override via STJORI/NOTANDI_PASSWORD_HASH in .env."""
    if role == ROLE_STJORI:
        return (
            os.environ.get("STJORI_PASSWORD_HASH")
            or os.environ.get("ADMIN_PASSWORD_HASH")
            or _STJORI_DEFAULT_HASH
        )
    return os.environ.get("NOTANDI_PASSWORD_HASH") or _NOTANDI_DEFAULT_HASH


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def stjori_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        if session.get("role") != ROLE_STJORI:
            flash("Aðeins Stjóri hefur aðgang að þessu.", "error")
            return redirect(url_for("board"))
        return f(*args, **kwargs)

    return decorated


def pwa_enabled() -> bool:
    return os.environ.get("PWA_ENABLED", "1").lower() in ("1", "true", "yes", "on")


def detail_inline_edit_enabled() -> bool:
    """Inline edit on order detail (no Breyta button). Revert: DETAIL_INLINE_EDIT=0"""
    return os.environ.get("DETAIL_INLINE_EDIT", "1").lower() in ("1", "true", "yes", "on")


_password_hash_for_role = password_hash_for_role


def inject_role_context():
    role = session.get("role")
    return {
        "role": role,
        "is_stjori": role == ROLE_STJORI,
        "is_notandi": role == ROLE_NOTANDI,
        "role_label": ROLE_LABELS.get(role, ""),
        "pwa_enabled": pwa_enabled(),
        "detail_inline_edit": detail_inline_edit_enabled(),
    }
