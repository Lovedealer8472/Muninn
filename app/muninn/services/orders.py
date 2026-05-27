"""Order business logic and board helpers."""

import os
import shutil
import uuid
from datetime import datetime
from typing import Optional

import mimetypes

from flask import request, session, url_for
from werkzeug.utils import secure_filename

from muninn.config import (
    ALLOWED_EXT,
    AUTO_EMAIL_STATUS,
    CONTACT_SHORT,
    EVENT_FIELD_LABELS,
    upload_root_for,
)

# Set by init_app
UPLOAD_ROOT: str = ""


def init_app(app) -> None:
    global UPLOAD_ROOT
    UPLOAD_ROOT = upload_root_for(app)
    os.makedirs(UPLOAD_ROOT, exist_ok=True)


def should_auto_notify_customer(order, new_status: str) -> bool:
    """Send email automatically only when status becomes Komið (unless suppressed after trash restore)."""
    if new_status != AUTO_EMAIL_STATUS:
        return False
    suppressed = bool(order["suppress_auto_email"]) if "suppress_auto_email" in order.keys() else False
    return not suppressed


def clear_email_suppress(db, order_id: int) -> None:
    db.execute(
        "UPDATE orders SET suppress_auto_email = 0 WHERE id = ?", (order_id,)
    )


def can_archive_order(order) -> bool:
    """Ready to clear from board: delivered and paid in full."""
    return order["status"] == "Lokið" and order["payment_status"] == "Greitt"


def pop_archive_prompt(order_id: int) -> bool:
    return bool(session.pop(f"archive_prompt_{order_id}", None))


def get_order(db, order_id, *, include_deleted=False):
    if include_deleted:
        return db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return db.execute(
        "SELECT * FROM orders WHERE id = ? AND deleted_at IS NULL",
        (order_id,),
    ).fetchone()


def log_order_event(db, order_id, field_name, old_value, new_value):
    old_value = (old_value or "").strip()
    new_value = (new_value or "").strip()
    if field_name != "_created" and old_value == new_value:
        return
    now = datetime.now().isoformat(timespec="seconds")
    db.execute(
        """
        INSERT INTO order_events (order_id, field_name, old_value, new_value, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (order_id, field_name, old_value, new_value, now),
    )


def log_tracked_changes(db, order_id, before, after):
    """Log changes for tracked fields between two order rows or dicts."""
    for field in EVENT_FIELD_LABELS:
        if field.startswith("_"):
            continue
        old_v = (before[field] if field in before.keys() else "") or ""
        new_v = (after[field] if field in after.keys() else "") or ""
        if str(old_v).strip() != str(new_v).strip():
            log_order_event(db, order_id, field, str(old_v), str(new_v))


def patch_order_fields(db, order_id, order, updates: dict) -> None:
    """Apply partial field updates with saga logging."""
    if not updates:
        return
    now = datetime.now().isoformat(timespec="seconds")
    after = dict(order)
    after.update(updates)
    log_tracked_changes(db, order_id, order, after)
    assignments = ", ".join(f"{key}=?" for key in updates)
    params = [updates[key] for key in updates] + [now, order_id]
    db.execute(
        f"UPDATE orders SET {assignments}, updated_at=? WHERE id=?",
        params,
    )


def get_order_events(db, order_id, limit=10):
    return db.execute(
        """
        SELECT * FROM order_events
        WHERE order_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (order_id, limit),
    ).fetchall()


def get_order_comments(db, order_id, limit=200):
    return db.execute(
        """
        SELECT * FROM order_comments
        WHERE order_id = ?
        ORDER BY created_at ASC, id ASC
        LIMIT ?
        """,
        (order_id, limit),
    ).fetchall()


def track_public_url():
    base = os.environ.get("TRACK_PUBLIC_URL", "").strip().rstrip("/")
    if base:
        return f"{base}{url_for('track')}"
    return request.url_root.rstrip("/") + url_for("track")


def order_card_view(row, today: str) -> dict:
    """Enrich order row for board card display."""
    o = dict(row)
    ts = (row["updated_at"] or row["created_at"] or "")[:19]
    try:
        idle_days = max(0, (datetime.now() - datetime.fromisoformat(ts)).days)
    except ValueError:
        idle_days = 0
    o["idle_days"] = idle_days
    o["is_overdue"] = bool(
        row["estimated_arrival"]
        and row["estimated_arrival"] < today
        and row["status"] not in ("Komið", "Lokið")
    )
    o["is_pickup"] = row["status"] == "Komið"
    cs = row["contact_status"] or ""
    o["contact_short"] = CONTACT_SHORT.get(cs, cs[:12] if cs else "")
    o["comment_count"] = int(row["comment_count"]) if "comment_count" in row.keys() else 0
    return o


def board_orders_query(db, query, stale_days=None):
    comment_join = """
        LEFT JOIN (
            SELECT order_id, COUNT(*) AS comment_count
            FROM order_comments
            GROUP BY order_id
        ) cc ON cc.order_id = orders.id
    """
    stale_clause = ""
    stale_params = []
    if stale_days is not None and stale_days > 0:
        stale_clause = (
            " AND datetime(COALESCE(updated_at, created_at)) "
            "<= datetime('now', ?)"
        )
        stale_params.append(f"-{int(stale_days)} days")

    order_by_stale = ""
    if stale_days is not None and stale_days > 0:
        order_by_stale = "updated_at ASC, "

    select_cols = "orders.*, COALESCE(cc.comment_count, 0) AS comment_count"

    if query:
        like = f"%{query}%"
        phone_digits = digits_only(query)
        phone_clause = ""
        params = [like, like, like, like, like, like, like]
        if len(phone_digits) >= 3:
            phone_clause = (
                " OR REPLACE(REPLACE(REPLACE(REPLACE(phone, ' ', ''), '-', ''), "
                "'(', ''), ')', '') LIKE ?"
            )
            params.append(f"%{phone_digits}%")
        params.extend(stale_params)
        return db.execute(
            f"""
            SELECT {select_cols} FROM orders
            {comment_join}
            WHERE deleted_at IS NULL
              AND (customer_name LIKE ?
               OR phone LIKE ?
               OR email LIKE ?
               OR product_name LIKE ?
               OR product_model LIKE ?
               OR supplier LIKE ?
               OR notes LIKE ?{phone_clause}){stale_clause}
            ORDER BY
                {order_by_stale}
                CASE priority
                    WHEN 'Brýnt' THEN 0
                    WHEN 'Mikilvægt' THEN 1
                    ELSE 2
                END,
                created_at DESC
            """,
            tuple(params),
        ).fetchall()
    return db.execute(
        f"""
        SELECT {select_cols} FROM orders
        {comment_join}
        WHERE deleted_at IS NULL{stale_clause}
        ORDER BY
            {order_by_stale}
            CASE priority
                WHEN 'Brýnt' THEN 0
                WHEN 'Mikilvægt' THEN 1
                ELSE 2
            END,
            created_at DESC
        """,
        tuple(stale_params),
    ).fetchall()


def parse_stale_days(raw) -> Optional[int]:
    if raw is None or raw == "":
        return None
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return None
    return days if days > 0 else None


def board_version_for_rows(rows, query, stale_days=None):
    count = len(rows)
    max_updated = max((r["updated_at"] for r in rows), default="")
    stale = stale_days if stale_days is not None else ""
    return f"{count}:{max_updated}:{query}:{stale}"


def trash_count(db):
    return db.execute(
        "SELECT COUNT(*) AS c FROM orders WHERE deleted_at IS NOT NULL"
    ).fetchone()["c"]


def digits_only(s):
    return "".join(c for c in (s or "") if c.isdigit())


def phone_matches(query_digits, stored_phone):
    """Lightweight match: full digit equality or same last 7 digits (Iceland mobiles)."""
    db_digits = digits_only(stored_phone)
    if not query_digits or not db_digits:
        return False
    if query_digits == db_digits:
        return True
    if len(query_digits) >= 7 and len(db_digits) >= 7:
        return query_digits[-7:] == db_digits[-7:]
    return query_digits == db_digits


def allowed_filename(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def order_upload_dir(order_id: int) -> str:
    path = os.path.join(UPLOAD_ROOT, str(order_id))
    os.makedirs(path, exist_ok=True)
    return path


def hard_delete_order(db, order_id):
    db.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    db.commit()
    upload_dir = order_upload_dir(order_id)
    if os.path.isdir(upload_dir):
        shutil.rmtree(upload_dir, ignore_errors=True)


def attachment_payload(row, order_id):
    return {
        "id": row["id"],
        "filename": row["filename"],
        "size_bytes": row["size_bytes"],
        "mime_type": row["mime_type"],
        "uploaded_at": row["uploaded_at"],
        "url": url_for("attachment_download", order_id=order_id, att_id=row["id"]),
        "delete_url": url_for(
            "attachment_delete", order_id=order_id, att_id=row["id"]
        ),
    }
