"""Order CRUD and workflow routes."""

import os
from datetime import datetime

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for

from muninn.auth import detail_inline_edit_enabled, login_required, stjori_required
from muninn.config import (
    CONTACT_OPTIONS,
    EVENT_FIELD_LABELS,
    INLINE_EDIT_SECTIONS,
    PAYMENT_OPTIONS,
    PRIORITY_OPTIONS,
    ROLE_NOTANDI,
    STATUSES,
    STATUS_HELP,
    TRASH_RETENTION_DAYS,
)
from muninn.db import get_db
from muninn.services.email import dispatch_customer_email, pop_email_notice
from muninn.services.orders import (
    can_archive_order,
    get_order,
    get_order_comments,
    get_order_events,
    hard_delete_order,
    log_order_event,
    log_tracked_changes,
    patch_order_fields,
    pop_archive_prompt,
    should_auto_notify_customer,
    track_public_url,
)

def register(app: Flask) -> None:

    @app.route("/order/new", methods=["GET", "POST"])
    @login_required
    def order_new():
        if request.method == "POST":
            now = datetime.now().isoformat(timespec="seconds")
            db = get_db()
            cur = db.execute(
                """
                INSERT INTO orders
                    (customer_name, phone, email, product_name, product_model,
                     supplier, status, date_requested, date_ordered,
                     estimated_arrival, date_arrived, date_completed,
                     payment_status, contact_status, priority, notes,
                     created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    request.form["customer_name"].strip(),
                    request.form.get("phone", "").strip(),
                    request.form.get("email", "").strip(),
                    request.form["product_name"].strip(),
                    request.form.get("product_model", "").strip(),
                    request.form.get("supplier", "").strip(),
                    "Móttekið",
                    request.form.get("date_requested", ""),
                    "",
                    "",
                    "",
                    "",
                    request.form.get("payment_status", "Ógreitt"),
                    "Ekki haft samband",
                    request.form.get("priority", "Venjulegt"),
                    request.form.get("notes", "").strip(),
                    now,
                    now,
                ),
            )
            log_order_event(db, cur.lastrowid, "_created", "", "Pöntun stofnuð")
            db.commit()
            flash("Pöntun búin til.", "success")
            return redirect(url_for("board"))

        today = datetime.now().strftime("%Y-%m-%d")
        return render_template(
            "order_form.html",
            order=None,
            statuses=STATUSES,
            payment_options=PAYMENT_OPTIONS,
            contact_options=CONTACT_OPTIONS,
            priority_options=PRIORITY_OPTIONS,
            today=today,
        )


    @app.route("/order/<int:order_id>")
    @login_required
    def order_detail(order_id):
        db = get_db()
        order = get_order(db, order_id)
        if order is None:
            abort(404)

        today = datetime.now().strftime("%Y-%m-%d")
        status_idx = STATUSES.index(order["status"]) if order["status"] in STATUSES else 0
        events = get_order_events(db, order_id, limit=25)
        comments = get_order_comments(db, order_id)
        track_url = track_public_url()
        return render_template(
            "order_detail.html",
            order=order,
            statuses=STATUSES,
            status_idx=status_idx,
            payment_options=PAYMENT_OPTIONS,
            contact_options=CONTACT_OPTIONS,
            priority_options=PRIORITY_OPTIONS,
            today=today,
            events=events,
            event_labels=EVENT_FIELD_LABELS,
            comments=comments,
            track_url=track_url,
            status_help=STATUS_HELP,
            email_notice=pop_email_notice(order_id),
            can_archive=can_archive_order(order),
            show_archive_prompt=pop_archive_prompt(order_id),
        )


    @app.route("/order/<int:order_id>/comments", methods=["POST"])
    @login_required
    def order_comment_add(order_id):
        body = request.form.get("body", "").strip()
        if not body:
            flash("Athugasemd má ekki vera tóm.", "error")
            return redirect(url_for("order_detail", order_id=order_id))

        db = get_db()
        order = get_order(db, order_id)
        if order is None:
            abort(404)

        if len(body) > 4000:
            body = body[:4000]
        now = datetime.now().isoformat(timespec="seconds")
        author = session.get("user", "admin")
        db.execute(
            """
            INSERT INTO order_comments (order_id, body, author, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (order_id, body, author, now),
        )
        preview = body.replace("\n", " ")[:120]
        if len(body) > 120:
            preview += "…"
        log_order_event(db, order_id, "_comment", "", preview)
        db.execute("UPDATE orders SET updated_at = ? WHERE id = ?", (now, order_id))
        db.commit()
        flash("Athugasemd skráð.", "success")
        return redirect(url_for("order_detail", order_id=order_id))


    @app.route("/order/<int:order_id>/print")
    @login_required
    def order_print(order_id):
        db = get_db()
        order = get_order(db, order_id)
        if order is None:
            abort(404)
        printed_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        return render_template(
            "order_print.html",
            order=order,
            printed_at=printed_at,
            printed_by=session.get("user", "admin"),
            shop_name=os.environ.get("SHOP_NAME", "Muninn"),
        )


    @app.route("/order/<int:order_id>/inline/<section>", methods=["POST"])
    @login_required
    def order_inline_update(order_id, section):
        if not detail_inline_edit_enabled():
            abort(404)
        fields = INLINE_EDIT_SECTIONS.get(section)
        if not fields:
            abort(404)

        db = get_db()
        order = get_order(db, order_id)
        if order is None:
            abort(404)

        updates = {}
        for field in fields:
            if field not in request.form:
                continue
            updates[field] = request.form.get(field, "").strip()

        if section == "customer":
            name = updates.get("customer_name", order["customer_name"] or "").strip()
            if not name:
                flash("Nafn viðskiptavinar má ekki vera tómt.", "error")
                return redirect(url_for("order_detail", order_id=order_id))
            updates["customer_name"] = name
        elif section == "product":
            product = updates.get("product_name", order["product_name"] or "").strip()
            if not product:
                flash("Heiti vöru má ekki vera tómt.", "error")
                return redirect(url_for("order_detail", order_id=order_id))
            updates["product_name"] = product

        patch_order_fields(db, order_id, order, updates)
        db.commit()
        flash("Breyting vistuð.", "success")
        return redirect(url_for("order_detail", order_id=order_id))


    @app.route("/order/<int:order_id>/priority", methods=["POST"])
    @login_required
    def order_priority(order_id):
        new_value = request.form.get("priority", "")
        if new_value not in PRIORITY_OPTIONS:
            abort(400)

        db = get_db()
        order = get_order(db, order_id)
        if order is None:
            abort(404)
        patch_order_fields(db, order_id, order, {"priority": new_value})
        db.commit()
        return redirect(url_for("order_detail", order_id=order_id))


    @app.route("/order/<int:order_id>/edit", methods=["GET", "POST"])
    @login_required
    def order_edit(order_id):
        db = get_db()
        order = get_order(db, order_id)
        if order is None:
            abort(404)

        if request.method == "POST":
            now = datetime.now().isoformat(timespec="seconds")
            after = {
                "status": request.form.get("status", order["status"]),
                "payment_status": request.form.get("payment_status", "Ógreitt"),
                "contact_status": request.form.get(
                    "contact_status", "Ekki haft samband"
                ),
                "priority": request.form.get("priority", "Venjulegt"),
                "estimated_arrival": request.form.get("estimated_arrival", ""),
            }
            log_tracked_changes(db, order_id, order, after)
            db.execute(
                """
                UPDATE orders SET
                    customer_name=?, phone=?, email=?, product_name=?,
                    product_model=?, supplier=?, status=?,
                    date_requested=?, date_ordered=?, estimated_arrival=?,
                    date_arrived=?, date_completed=?,
                    payment_status=?, contact_status=?, priority=?, notes=?,
                    updated_at=?
                WHERE id=?
                """,
                (
                    request.form["customer_name"].strip(),
                    request.form.get("phone", "").strip(),
                    request.form.get("email", "").strip(),
                    request.form["product_name"].strip(),
                    request.form.get("product_model", "").strip(),
                    request.form.get("supplier", "").strip(),
                    after["status"],
                    request.form.get("date_requested", ""),
                    request.form.get("date_ordered", ""),
                    after["estimated_arrival"],
                    request.form.get("date_arrived", ""),
                    request.form.get("date_completed", ""),
                    after["payment_status"],
                    after["contact_status"],
                    after["priority"],
                    request.form.get("notes", "").strip(),
                    now,
                    order_id,
                ),
            )
            db.commit()

            updated_order = db.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            new_status = after["status"]
            if (
                should_auto_notify_customer(order, new_status)
                and order["status"] != new_status
            ):
                session[f"email_notice_{order_id}"] = dispatch_customer_email(
                    db, order_id, updated_order
                )
            if updated_order and can_archive_order(updated_order):
                session[f"archive_prompt_{order_id}"] = True
            flash("Pöntun uppfærð.", "success")
            return redirect(url_for("order_detail", order_id=order_id))

        today = datetime.now().strftime("%Y-%m-%d")
        return render_template(
            "order_form.html",
            order=order,
            statuses=STATUSES,
            payment_options=PAYMENT_OPTIONS,
            contact_options=CONTACT_OPTIONS,
            priority_options=PRIORITY_OPTIONS,
            today=today,
        )


    @app.route("/order/<int:order_id>/archive", methods=["POST"])
    @login_required
    def order_archive(order_id):
        db = get_db()
        order = get_order(db, order_id)
        if order is None:
            abort(404)
        if not can_archive_order(order):
            flash("Aðeins hægt að geyma pantanir sem eru Lokið og Greitt.", "error")
            return redirect(url_for("order_detail", order_id=order_id))
        now = datetime.now().isoformat(timespec="seconds")
        db.execute(
            "UPDATE orders SET deleted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, order_id),
        )
        log_order_event(db, order_id, "_archived", "", "Geymt af borði")
        db.commit()
        flash("Pöntun geymd — fjarlægð af borði. Stjóri getur endurheimt úr Rusl.", "success")
        return redirect(url_for("board"))


    @app.route("/order/<int:order_id>/delete", methods=["POST"])
    @login_required
    @stjori_required
    def order_delete(order_id):
        db = get_db()
        order = get_order(db, order_id)
        if order is None:
            abort(404)
        now = datetime.now().isoformat(timespec="seconds")
        db.execute(
            "UPDATE orders SET deleted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, order_id),
        )
        log_order_event(db, order_id, "_deleted", "", "Í rusl")
        db.commit()
        flash("Pöntun færð í rusl.", "success")
        return redirect(url_for("board"))


    @app.route("/trash")
    @login_required
    @stjori_required
    def trash():
        db = get_db()
        rows = db.execute(
            """
            SELECT * FROM orders
            WHERE deleted_at IS NOT NULL
            ORDER BY deleted_at DESC
            """
        ).fetchall()
        return render_template(
            "trash.html",
            orders=rows,
            retention_days=TRASH_RETENTION_DAYS,
        )


    @app.route("/order/<int:order_id>/restore", methods=["POST"])
    @login_required
    @stjori_required
    def order_restore(order_id):
        db = get_db()
        order = db.execute(
            "SELECT * FROM orders WHERE id = ? AND deleted_at IS NOT NULL",
            (order_id,),
        ).fetchone()
        if order is None:
            abort(404)
        now = datetime.now().isoformat(timespec="seconds")
        db.execute(
            "UPDATE orders SET deleted_at = NULL, updated_at = ?, suppress_auto_email = 1 WHERE id = ?",
            (now, order_id),
        )
        log_order_event(db, order_id, "_restored", "Í rusl", "Endurheimt")
        db.commit()
        flash("Pöntun endurheimt.", "success")
        return redirect(url_for("order_detail", order_id=order_id))


    @app.route("/order/<int:order_id>/purge", methods=["POST"])
    @login_required
    @stjori_required
    def order_purge(order_id):
        db = get_db()
        order = db.execute(
            "SELECT id FROM orders WHERE id = ? AND deleted_at IS NOT NULL",
            (order_id,),
        ).fetchone()
        if order is None:
            abort(404)
        hard_delete_order(db, order_id)
        flash("Pöntun eytt varanlega.", "success")
        return redirect(url_for("trash"))


    @app.route("/order/<int:order_id>/status", methods=["POST"])
    @login_required
    def order_status(order_id):
        new_status = request.form.get("status", "")
        if new_status not in STATUSES:
            abort(400)

        board_api = request.headers.get("X-Muninn-Board") == "1"

        db = get_db()
        order = get_order(db, order_id)
        if order is None:
            if board_api:
                return jsonify({"ok": False, "error": "Pöntun fannst ekki."}), 404
            abort(404)

        if session.get("role") == ROLE_NOTANDI:
            status_idx = (
                STATUSES.index(order["status"]) if order["status"] in STATUSES else 0
            )
            next_status = (
                STATUSES[status_idx + 1] if status_idx < len(STATUSES) - 1 else None
            )
            if new_status != next_status:
                msg = "Notandi getur aðeins fært pöntun áfram um eitt skref."
                if board_api:
                    return jsonify({"ok": False, "error": msg}), 403
                flash(msg, "error")
                return redirect(url_for("order_detail", order_id=order_id))

        if order["status"] == new_status:
            if board_api:
                return jsonify({"ok": True, "order_id": order_id, "status": new_status})
            return redirect(url_for("order_detail", order_id=order_id))

        now = datetime.now().isoformat(timespec="seconds")
        extra_updates = ""
        params = [new_status, now]

        if new_status == "Lokið" and not order["date_completed"]:
            extra_updates = ", date_completed=?"
            params.append(datetime.now().strftime("%Y-%m-%d"))

        params.append(order_id)
        log_order_event(db, order_id, "status", order["status"], new_status)
        db.execute(
            f"UPDATE orders SET status=?, updated_at=?{extra_updates} WHERE id=?",
            params,
        )
        db.commit()

        email_result = None
        if should_auto_notify_customer(order, new_status):
            updated_order = db.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            email_result = dispatch_customer_email(db, order_id, updated_order)

        if board_api:
            updated = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            return jsonify(
                {
                    "ok": True,
                    "order_id": order_id,
                    "status": new_status,
                    "email": email_result,
                    "archive_eligible": bool(updated and can_archive_order(updated)),
                }
            )

        if email_result is not None:
            session[f"email_notice_{order_id}"] = email_result
        updated = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if updated and can_archive_order(updated):
            session[f"archive_prompt_{order_id}"] = True
        flash("Staða uppfærð.", "success")
        return redirect(url_for("order_detail", order_id=order_id))


    @app.route("/order/<int:order_id>/send-email", methods=["POST"])
    @login_required
    def order_send_email(order_id):
        db = get_db()
        order = get_order(db, order_id)
        if order is None:
            abort(404)
        session[f"email_notice_{order_id}"] = dispatch_customer_email(
            db, order_id, order, manual=True
        )
        return redirect(url_for("order_detail", order_id=order_id))


    @app.route("/order/<int:order_id>/contact_status", methods=["POST"])
    @login_required
    def order_contact_status(order_id):
        new_value = request.form.get("contact_status", "")
        if new_value not in CONTACT_OPTIONS:
            abort(400)

        db = get_db()
        db_order = get_order(db, order_id)
        if db_order is None:
            abort(404)
        now = datetime.now().isoformat(timespec="seconds")
        if db_order and db_order["contact_status"] != new_value:
            log_order_event(
                db,
                order_id,
                "contact_status",
                db_order["contact_status"],
                new_value,
            )
        db.execute(
            "UPDATE orders SET contact_status=?, updated_at=? WHERE id=?",
            (new_value, now, order_id),
        )
        db.commit()
        return redirect(url_for("order_detail", order_id=order_id))


    @app.route("/order/<int:order_id>/payment_status", methods=["POST"])
    @login_required
    def order_payment_status(order_id):
        new_value = request.form.get("payment_status", "")
        if new_value not in PAYMENT_OPTIONS:
            abort(400)

        db = get_db()
        db_order = get_order(db, order_id)
        if db_order is None:
            abort(404)
        now = datetime.now().isoformat(timespec="seconds")
        if db_order["payment_status"] != new_value:
            log_order_event(
                db,
                order_id,
                "payment_status",
                db_order["payment_status"],
                new_value,
            )
        db.execute(
            "UPDATE orders SET payment_status=?, updated_at=? WHERE id=?",
            (new_value, now, order_id),
        )
        db.commit()
        updated = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if updated and can_archive_order(updated):
            session[f"archive_prompt_{order_id}"] = True
        return redirect(url_for("order_detail", order_id=order_id))
