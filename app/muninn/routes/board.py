"""Board and stats routes."""

from datetime import datetime, timedelta

from flask import Flask, render_template, request

from muninn.auth import login_required, stjori_required
from muninn.config import STATUSES, STATUS_HELP
from muninn.db import get_db
from muninn.services.orders import (
    board_orders_query,
    board_version_for_rows,
    order_card_view,
    parse_stale_days,
    trash_count,
)


def register(app: Flask) -> None:
    @app.route("/")
    @login_required
    def board():
        db = get_db()
        query = request.args.get("q", "").strip()
        stale_days = parse_stale_days(request.args.get("stale"))
        rows = board_orders_query(db, query, stale_days)

        today = datetime.now().strftime("%Y-%m-%d")
        columns = {s: [] for s in STATUSES}
        for row in rows:
            status = row["status"]
            if status in columns:
                columns[status].append(order_card_view(row, today))

        board_version = board_version_for_rows(rows, query, stale_days)
        return render_template(
            "board.html",
            columns=columns,
            statuses=STATUSES,
            status_help=STATUS_HELP,
            query=query,
            stale_days=stale_days,
            today=today,
            board_version=board_version,
            trash_count=trash_count(db),
        )

    @app.route("/stats")
    @login_required
    @stjori_required
    def stats():
        db = get_db()
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now()

        status_counts = {s: 0 for s in STATUSES}
        for row in db.execute(
            "SELECT status, COUNT(*) AS c FROM orders WHERE deleted_at IS NULL GROUP BY status"
        ).fetchall():
            if row["status"] in status_counts:
                status_counts[row["status"]] = row["c"]

        overdue = db.execute(
            """
            SELECT COUNT(*) AS c FROM orders
            WHERE deleted_at IS NULL
              AND estimated_arrival != ''
              AND estimated_arrival < ?
              AND status NOT IN ('Komið', 'Lokið')
            """,
            (today,),
        ).fetchone()["c"]

        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        month_start = now.strftime("%Y-%m-01")

        completed_week = db.execute(
            """
            SELECT COUNT(*) AS c FROM orders
            WHERE deleted_at IS NULL
              AND status = 'Lokið'
              AND date_completed != ''
              AND date_completed >= ?
            """,
            (week_start,),
        ).fetchone()["c"]

        completed_month = db.execute(
            """
            SELECT COUNT(*) AS c FROM orders
            WHERE deleted_at IS NULL
              AND status = 'Lokið'
              AND date_completed != ''
              AND date_completed >= ?
            """,
            (month_start,),
        ).fetchone()["c"]

        avg_days_row = db.execute(
            """
            SELECT AVG(
                julianday(date_completed) - julianday(date_ordered)
            ) AS avg_days
            FROM orders
            WHERE deleted_at IS NULL
              AND status = 'Lokið'
              AND date_ordered != ''
              AND date_completed != ''
            """
        ).fetchone()
        avg_days = avg_days_row["avg_days"]
        avg_days_display = f"{avg_days:.1f}" if avg_days is not None else "–"

        unpaid_active = db.execute(
            """
            SELECT COUNT(*) AS c FROM orders
            WHERE deleted_at IS NULL
              AND payment_status = 'Ógreitt'
              AND status != 'Lokið'
            """
        ).fetchone()["c"]

        total_open = sum(
            status_counts[s] for s in STATUSES if s != "Lokið"
        )

        return render_template(
            "stats.html",
            status_counts=status_counts,
            statuses=STATUSES,
            overdue=overdue,
            completed_week=completed_week,
            completed_month=completed_month,
            avg_days_display=avg_days_display,
            unpaid_active=unpaid_active,
            total_open=total_open,
            today=today,
        )
