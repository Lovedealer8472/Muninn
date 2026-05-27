"""JSON API routes."""

from flask import Flask, abort, jsonify, request

from muninn.auth import login_required
from muninn.config import EMAIL_NOTICE
from muninn.db import get_db
from muninn.services.email import latest_email_notify_result
from muninn.services.orders import (
    board_orders_query,
    board_version_for_rows,
    get_order,
    parse_stale_days,
)


def register(app: Flask) -> None:
    @app.route("/api/board/version")
    @login_required
    def board_version_api():
        db = get_db()
        query = request.args.get("q", "").strip()
        stale_days = parse_stale_days(request.args.get("stale"))
        rows = board_orders_query(db, query, stale_days)
        return jsonify({"version": board_version_for_rows(rows, query, stale_days)})

    @app.route("/api/order/<int:order_id>/notification-status")
    @login_required
    def order_notification_status_api(order_id):
        db = get_db()
        if get_order(db, order_id) is None:
            abort(404)
        result = latest_email_notify_result(db, order_id)
        if not result or result == "pending":
            return jsonify({"status": "pending"})
        if result not in EMAIL_NOTICE:
            return jsonify({"status": "done", "result": result, "text": result, "kind": "info"})
        text, kind = EMAIL_NOTICE[result]
        return jsonify({"status": "done", "result": result, "text": text, "kind": kind})
