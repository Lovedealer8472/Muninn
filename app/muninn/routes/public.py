"""Public tracking routes."""

from flask import Flask, flash, render_template, request

from muninn.db import get_db
from muninn.services.orders import digits_only, phone_matches, track_public_url


def register(app: Flask) -> None:
    @app.route("/track", methods=["GET", "POST"])
    def track():
        """Public lookup: símanúmer → listi pantana (einfalt, án innskráningar)."""
        if request.method == "POST":
            raw_phone = request.form.get("phone", "").strip()
            qdigits = digits_only(raw_phone)

            if len(qdigits) < 3:
                flash("Sláðu inn gilt símanúmer (að minnsta kosti 3 tölustafir).", "error")
                return render_template("track.html", orders=None)

            db = get_db()
            rows = db.execute(
                """
                SELECT id, product_name, status, estimated_arrival, payment_status, phone, deleted_at
                FROM orders
                WHERE deleted_at IS NULL
                  AND TRIM(COALESCE(phone, '')) != ''
                ORDER BY created_at DESC
                """
            ).fetchall()

            orders = [
                r for r in rows
                if r["deleted_at"] is None and phone_matches(qdigits, r["phone"])
            ]

            if not orders:
                flash("Engar pantanir fundust fyrir þetta númer.", "error")

            return render_template(
                "track.html", orders=orders, track_url=track_public_url()
            )

        return render_template("track.html", orders=None, track_url=track_public_url())
