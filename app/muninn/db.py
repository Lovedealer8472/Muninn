"""SQLite database setup and helpers."""

import os
import sqlite3
from datetime import datetime, timedelta

from flask import Flask, g

from muninn.config import TRASH_RETENTION_DAYS

DATABASE: str = ""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name       TEXT NOT NULL,
    phone               TEXT DEFAULT '',
    email               TEXT DEFAULT '',
    product_name        TEXT NOT NULL,
    product_model       TEXT DEFAULT '',
    supplier            TEXT DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'Móttekið',
    date_requested      TEXT DEFAULT '',
    date_ordered        TEXT DEFAULT '',
    estimated_arrival   TEXT DEFAULT '',
    date_arrived        TEXT DEFAULT '',
    date_completed      TEXT DEFAULT '',
    payment_status      TEXT DEFAULT 'Ógreitt',
    contact_status      TEXT DEFAULT 'Ekki haft samband',
    priority            TEXT DEFAULT 'Venjulegt',
    notes               TEXT DEFAULT '',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    deleted_at          TEXT
);

CREATE TABLE IF NOT EXISTS attachments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    stored_name   TEXT NOT NULL,
    mime_type     TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    uploaded_by   TEXT NOT NULL DEFAULT 'admin',
    uploaded_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attachments_order ON attachments(order_id);

CREATE TABLE IF NOT EXISTS order_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    field_name  TEXT NOT NULL,
    old_value   TEXT DEFAULT '',
    new_value   TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_order_events_order ON order_events(order_id);

CREATE TABLE IF NOT EXISTS order_comments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    body        TEXT NOT NULL,
    author      TEXT NOT NULL DEFAULT 'admin',
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_order_comments_order ON order_comments(order_id);
"""


def init_app(app: Flask) -> None:
    global DATABASE
    if "DATABASE" not in app.config:
        app.config["DATABASE"] = os.path.join(app.root_path, "pantanakerfi.db")
    DATABASE = app.config["DATABASE"]
    app.teardown_appcontext(close_db)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
        _ensure_schema(g.db)
        _purge_expired_trash(g.db)
    return g.db


def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def bootstrap_database() -> None:
    """Ensure tables exist at startup (replaces import-time init in app.py)."""
    conn = sqlite3.connect(DATABASE)
    conn.executescript(SCHEMA_SQL)
    _ensure_schema(conn)
    conn.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA_SQL)
    db.commit()


def _ensure_schema(conn):
    """Ensure tables exist and apply column migrations for older databases."""
    conn.executescript(SCHEMA_SQL)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(orders)").fetchall()]
    if "deleted_at" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN deleted_at TEXT")
    if "suppress_auto_email" not in cols:
        conn.execute(
            "ALTER TABLE orders ADD COLUMN suppress_auto_email INTEGER NOT NULL DEFAULT 0"
        )
    conn.commit()


def _purge_expired_trash(db):
    from muninn.services.orders import hard_delete_order

    cutoff = (
        datetime.now() - timedelta(days=TRASH_RETENTION_DAYS)
    ).isoformat(timespec="seconds")
    expired = db.execute(
        "SELECT id FROM orders WHERE deleted_at IS NOT NULL AND deleted_at < ?",
        (cutoff,),
    ).fetchall()
    for row in expired:
        hard_delete_order(db, row["id"])
