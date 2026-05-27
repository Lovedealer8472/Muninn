"""Authentication routes."""

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from muninn.auth import password_hash_for_role
from muninn.config import ROLE_LABELS, ROLE_NOTANDI, ROLE_STJORI


def register(app: Flask) -> None:
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            password = request.form.get("password", "")
            role = request.form.get("role", ROLE_NOTANDI)
            if role not in (ROLE_STJORI, ROLE_NOTANDI):
                role = ROLE_NOTANDI
            if check_password_hash(password_hash_for_role(role), password):
                session["logged_in"] = True
                session["role"] = role
                session["user"] = ROLE_LABELS[role]
                return redirect(url_for("board"))
            flash("Rangt lykilorð fyrir valda aðgang.", "error")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))
