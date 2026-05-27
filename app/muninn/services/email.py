"""Email and SMTP services."""

import logging
import os
import smtplib
import sqlite3
import threading
from datetime import datetime
from email.message import EmailMessage
from typing import Optional

from customer_email import build_customer_notification
from flask import flash, has_request_context

from muninn.config import AUTO_EMAIL_STATUS, EMAIL_NOTICE, EMAIL_SAGA_SKIP
from muninn.db import DATABASE
from muninn.services.orders import log_order_event, track_public_url

logger = logging.getLogger("muninn.email")

_app = None


def init_app(app) -> None:
    global _app
    _app = app


def smtp_config():
    return {
        "server": os.environ.get("SMTP_SERVER"),
        "port": int(os.environ.get("SMTP_PORT", 587)),
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASS"),
        "from": os.environ.get("SMTP_FROM", "no-reply@tolvuhvislarinn.is"),
        "shop_name": os.environ.get("SHOP_NAME", "Verslunin"),
    }


def send_email(to_email, subject, text_body, html_body=None):
    cfg = smtp_config()
    if not cfg["server"] or not cfg["user"] or not cfg["password"] or not to_email:
        return False
    msg = EmailMessage()
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    msg["Subject"] = subject
    msg["From"] = f"{cfg['shop_name']} <{cfg['from']}>"
    msg["To"] = to_email
    try:
        server = smtplib.SMTP(cfg["server"], cfg["port"])
        server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception:
        logger.exception("SMTP send failed")
        return False


def customer_track_url() -> str:
    base = os.environ.get("TRACK_PUBLIC_URL", "").strip().rstrip("/")
    if base:
        return f"{base}/track" if not base.endswith("/track") else base
    if has_request_context():
        return track_public_url()
    return "https://th.tolvuhvislarinn.is/track"


def order_dict(order) -> dict:
    return order if isinstance(order, dict) else dict(order)


def build_notification_message(order, *, manual: bool = False):
    """Return (to_email, subject, text_body, html_body) or None."""
    order = order_dict(order)
    cfg = smtp_config()
    if not cfg["server"] or not cfg["user"] or not cfg["password"]:
        return None
    status = order["status"]
    if not manual and status != AUTO_EMAIL_STATUS:
        return None
    track_url = (
        customer_track_url() if manual and status not in ("Staðfest", "Komið") else None
    )
    return build_customer_notification(order, track_url=track_url)


def preview_email_result(order, *, manual: bool = False) -> str:
    """Immediate result without SMTP (skipped / config / no address)."""
    if not manual and order["status"] != AUTO_EMAIL_STATUS:
        return "skipped"
    if not (order["email"] or "").strip():
        return "no_email"
    cfg = smtp_config()
    if not cfg["server"] or not cfg["user"] or not cfg["password"]:
        return "no_smtp"
    if not build_notification_message(order, manual=manual):
        return "skipped"
    return "pending"


def email_saga_text(order, result: str) -> Optional[str]:
    if result in EMAIL_SAGA_SKIP:
        return None
    status = (order.get("status") if isinstance(order, dict) else order["status"]) or ""
    email = (
        (order.get("email") if isinstance(order, dict) else order["email"]) or ""
    ).strip()
    if result == "sent":
        if email:
            return f"Sendt til {email} — stöða: {status}"
        return f"Sendt til viðskiptavinar — stöða: {status}"
    if result == "failed":
        target = email or "viðskiptavinar"
        return f"Mistókst að senda til {target} — stöða: {status}"
    if result == "no_email":
        return f"Ekki sent (ekki netfang) — stöða: {status}"
    if result == "no_smtp":
        return f"Ekki sent (SMTP ekki stillt) — stöða: {status}"
    return None


def log_email_notify_event(db, order_id: int, order, result: str) -> None:
    text = email_saga_text(order, result)
    if text:
        log_order_event(db, order_id, "_email_notify", "", text)


def queue_customer_email(order_id: int, order: dict, *, manual: bool = False) -> None:
    def work():
        with _app.app_context():
            result = "failed"
            try:
                built = build_notification_message(order, manual=manual)
                if not built:
                    result = "skipped"
                else:
                    to_email, subject, text_body, html_body = built
                    result = (
                        "sent"
                        if send_email(to_email, subject, text_body, html_body)
                        else "failed"
                    )
            except Exception:
                logger.exception("Background email failed")
                result = "failed"
            conn = sqlite3.connect(DATABASE)
            text = email_saga_text(order, result)
            if text:
                now = datetime.now().isoformat(timespec="seconds")
                conn.execute(
                    """
                    INSERT INTO order_events
                        (order_id, field_name, old_value, new_value, created_at)
                    VALUES (?, '_email_notify', '', ?, ?)
                    """,
                    (order_id, text, now),
                )
            if result == "sent":
                conn.execute(
                    "UPDATE orders SET suppress_auto_email = 0 WHERE id = ?",
                    (order_id,),
                )
            conn.commit()
            conn.close()

    threading.Thread(target=work, daemon=True).start()


def dispatch_customer_email(db, order_id: int, order, *, manual: bool = False) -> str:
    """Queue SMTP in background when needed; return result code for UI."""
    order = order_dict(order)
    preview = preview_email_result(order, manual=manual)
    if preview != "pending":
        log_email_notify_event(db, order_id, order, preview)
        db.commit()
        return preview
    queue_customer_email(order_id, order, manual=manual)
    return "pending"


def send_notification_email(order, *, background=False) -> str:
    """Send status email. Returns: skipped | no_email | no_smtp | sent | failed | pending."""
    preview = preview_email_result(order)
    if preview != "pending":
        return preview

    built = build_notification_message(order)
    if not built:
        return "skipped"
    to_email, subject, text_body, html_body = built
    return "sent" if send_email(to_email, subject, text_body, html_body) else "failed"


def flash_email_result(result: str) -> None:
    messages = {
        "sent": ("Tilkynning send í tölvupósti til viðskiptavinar.", "success"),
        "failed": ("Póstur mistókst — reyndu aftur eða hringdu í viðskiptavin.", "error"),
        "no_email": ("Enginn póstur (ekki netfang skráð).", "info"),
        "no_smtp": ("Póstur ekki sendur (SMTP ekki stillt).", "warning"),
        "queued": ("Tilkynning send í bakgrunni.", "success"),
        "pending": ("Tilkynning sendist…", "pending"),
    }
    if result in messages:
        flash(*messages[result])


def latest_email_notify_result(db, order_id: int) -> Optional[str]:
    row = db.execute(
        """
        SELECT new_value FROM order_events
        WHERE order_id = ? AND field_name = '_email_notify'
        ORDER BY id DESC LIMIT 1
        """,
        (order_id,),
    ).fetchone()
    if not row:
        return None
    text = row["new_value"] or ""
    if text.startswith("Sendt til"):
        return "sent"
    if text.startswith("Mistókst"):
        return "failed"
    if "ekki netfang" in text:
        return "no_email"
    if "SMTP" in text:
        return "no_smtp"
    return "pending" if text == "pending" else None


def pop_email_notice(order_id: int) -> Optional[dict]:
    from flask import session

    result = session.pop(f"email_notice_{order_id}", None)
    if not result:
        return None
    if result == "pending":
        return {"text": EMAIL_NOTICE["pending"][0], "kind": "pending", "poll": True}
    if result not in EMAIL_NOTICE:
        return None
    text, kind = EMAIL_NOTICE[result]
    return {"text": text, "kind": kind, "poll": False}
