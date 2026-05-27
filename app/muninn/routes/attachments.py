"""Attachment upload and download routes."""

import mimetypes
import os
import uuid
from datetime import datetime

from flask import Flask, abort, flash, jsonify, redirect, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from muninn.auth import login_required
from muninn.db import get_db
from muninn.services.orders import (
    allowed_filename,
    attachment_payload,
    get_order,
    order_upload_dir,
)

def register(app: Flask) -> None:

    @app.route("/order/<int:order_id>/attachments", methods=["GET"])
    @login_required
    def attachment_list(order_id):
        db = get_db()
        if get_order(db, order_id) is None:
            abort(404)
        rows = db.execute(
            "SELECT * FROM attachments WHERE order_id = ? ORDER BY uploaded_at DESC, id DESC",
            (order_id,),
        ).fetchall()
        return jsonify([attachment_payload(r, order_id) for r in rows])


    @app.route("/order/<int:order_id>/attachments", methods=["POST"])
    @login_required
    def attachment_upload(order_id):
        db = get_db()
        if get_order(db, order_id) is None:
            abort(404)

        files = request.files.getlist("files")
        if not files:
            return jsonify({"error": "Engar skrár sendar."}), 400

        target_dir = order_upload_dir(order_id)
        now = datetime.now().isoformat(timespec="seconds")
        saved, rejected = [], []

        for fs in files:
            original = fs.filename or ""
            if not allowed_filename(original):
                rejected.append(
                    {"filename": original, "reason": "Tegund ekki leyfð."}
                )
                continue

            safe_name = secure_filename(original) or "file"
            ext = safe_name.rsplit(".", 1)[1].lower() if "." in safe_name else "bin"
            stored_name = f"{uuid.uuid4().hex}.{ext}"
            dest = os.path.join(target_dir, stored_name)
            fs.save(dest)
            try:
                os.chmod(dest, 0o640)
            except OSError:
                pass

            size_bytes = os.path.getsize(dest)
            mime_type = (
                fs.mimetype
                or mimetypes.guess_type(safe_name)[0]
                or "application/octet-stream"
            )

            cur = db.execute(
                """
                INSERT INTO attachments
                    (order_id, filename, stored_name, mime_type,
                     size_bytes, uploaded_by, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (order_id, safe_name, stored_name, mime_type, size_bytes, "admin", now),
            )
            att_id = cur.lastrowid
            row = db.execute(
                "SELECT * FROM attachments WHERE id = ?", (att_id,)
            ).fetchone()
            saved.append(attachment_payload(row, order_id))

        db.commit()
        return jsonify({"saved": saved, "rejected": rejected})


    @app.route("/order/<int:order_id>/attachments/<int:att_id>")
    @login_required
    def attachment_download(order_id, att_id):
        db = get_db()
        row = db.execute(
            "SELECT * FROM attachments WHERE id = ? AND order_id = ?",
            (att_id, order_id),
        ).fetchone()
        if row is None:
            abort(404)
        download = request.args.get("download") == "1"
        return send_from_directory(
            order_upload_dir(order_id),
            row["stored_name"],
            as_attachment=download,
            download_name=row["filename"],
            mimetype=row["mime_type"],
        )


    @app.route("/order/<int:order_id>/attachments/<int:att_id>/delete", methods=["POST"])
    @login_required
    def attachment_delete(order_id, att_id):
        db = get_db()
        row = db.execute(
            "SELECT * FROM attachments WHERE id = ? AND order_id = ?",
            (att_id, order_id),
        ).fetchone()
        if row is None:
            abort(404)

        file_path = os.path.join(order_upload_dir(order_id), row["stored_name"])
        try:
            os.remove(file_path)
        except FileNotFoundError:
            pass

        db.execute("DELETE FROM attachments WHERE id = ?", (att_id,))
        db.commit()

        wants_json = (
            request.headers.get("Accept", "").startswith("application/json")
            or request.headers.get("X-Requested-With") == "fetch"
        )
        if wants_json:
            return jsonify({"ok": True})

        flash("Viðhengi eytt.", "success")
        return redirect(url_for("order_detail", order_id=order_id))
