"""Public sandbox mode (DEMO_MODE=1 in .env)."""

from __future__ import annotations

import os


def demo_active() -> bool:
    return os.environ.get("DEMO_MODE", "").lower() in ("1", "true", "yes", "on")


def demo_context() -> dict:
    return {"demo_active": demo_active()}
