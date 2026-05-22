import mimetypes
import os
import shutil
import sqlite3
import threading
import uuid
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me")

DATABASE = os.path.join(app.root_path, "pantanakerfi.db")

_STJORI_DEFAULT_HASH = generate_password_hash("admin")
_NOTANDI_DEFAULT_HASH = generate_password_hash("user")

# ── Workflow constants ──────────────────────────────────────────────

STATUSES = [
    "Móttekið",
    "Í vinnslu",
    "Pantað",
    "Staðfest",
    "Komið",
    "Lokið",
]

PAYMENT_OPTIONS = ["Ógreitt", "Innborgun", "Greitt"]
CONTACT_OPTIONS = [
    "Ekki haft samband",
    "Haft samband",
    "Minnt á",
    "Næst ekki í viðskiptavin",
]
PRIORITY_OPTIONS = ["Venjulegt", "Mikilvægt", "Brýnt"]
TRASH_RETENTION_DAYS = 30

ROLE_STJORI = "stjori"
ROLE_NOTANDI = "notandi"
ROLE_LABELS = {
    ROLE_STJORI: "Stjóri",
    ROLE_NOTANDI: "Notandi",
}


def _password_hash_for_role(role: str) -> str:
    """Stjóri: admin. Notandi: user. Override via STJORI/NOTANDI_PASSWORD_HASH in .env."""
    if role == ROLE_STJORI:
        return (
            os.environ.get("STJORI_PASSWORD_HASH")
            or os.environ.get("ADMIN_PASSWORD_HASH")
            or _STJORI_DEFAULT_HASH
        )
    return os.environ.get("NOTANDI_PASSWORD_HASH") or _NOTANDI_DEFAULT_HASH

STATUS_HELP = {
    "Móttekið": "Ný beiðni móttekin.",
    "Í vinnslu": "Verið er að vinna málið innanhúss.",
    "Pantað": "Pöntun send til birgja.",
    "Staðfest": "Birgir staðfestir; áætluð koma gildir.",
    "Komið": "Vara komin — tilbúin til afhendingar.",
    "Lokið": "Lokið / afhent viðskiptavini.",
}

CONTACT_SHORT = {
    "Ekki haft samband": "Ekki samb.",
    "Haft samband": "Samb.",
    "Minnt á": "Minnt á",
    "Næst ekki í viðskiptavin": "Næst ekki",
}

# Fields recorded in order saga (audit log)
EVENT_FIELD_LABELS = {
    "status": "Staða",
    "payment_status": "Greiðslustaða",
    "contact_status": "Samskiptastaða",
    "priority": "Forgangur",
    "estimated_arrival": "Áætluð koma",
    "_created": "Stofnað",
    "_comment": "Ummæli",
}

# ── Attachments config ──────────────────────────────────────────────

UPLOAD_ROOT = os.path.join(app.root_path, "uploads")
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB per file
ALLOWED_EXT = {
    "pdf",
    "jpg", "jpeg", "png", "heic", "webp", "gif",
    "docx", "xlsx", "pptx", "doc", "xls", "ppt",
    "txt", "csv",
}
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
os.makedirs(UPLOAD_ROOT, exist_ok=True)

# ── Database helpers ────────────────────────────────────────────────


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
        _ensure_schema(g.db)
        _purge_expired_trash(g.db)
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
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
    )
    db.commit()


def _ensure_schema(conn):
    """Apply migrations for databases created before order_events existed."""
    conn.executescript(
        """
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
    )
    cols = [r[1] for r in conn.execute("PRAGMA table_info(orders)").fetchall()]
    if "deleted_at" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN deleted_at TEXT")
    conn.commit()


def _purge_expired_trash(db):
    cutoff = (
        datetime.now() - timedelta(days=TRASH_RETENTION_DAYS)
    ).isoformat(timespec="seconds")
    expired = db.execute(
        "SELECT id FROM orders WHERE deleted_at IS NOT NULL AND deleted_at < ?",
        (cutoff,),
    ).fetchall()
    for row in expired:
        _hard_delete_order(db, row["id"])


def _trash_count(db):
    return db.execute(
        "SELECT COUNT(*) AS c FROM orders WHERE deleted_at IS NOT NULL"
    ).fetchone()["c"]


def _get_order(db, order_id, *, include_deleted=False):
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
        if field == "_created":
            continue
        old_v = (before[field] if field in before.keys() else "") or ""
        new_v = (after[field] if field in after.keys() else "") or ""
        if str(old_v).strip() != str(new_v).strip():
            log_order_event(db, order_id, field, str(old_v), str(new_v))


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


def _order_card_view(row, today: str) -> dict:
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
    return o


def _board_orders_query(db, query):
    if query:
        like = f"%{query}%"
        phone_digits = _digits_only(query)
        phone_clause = ""
        params = [like, like, like, like, like, like, like]
        if len(phone_digits) >= 3:
            phone_clause = (
                " OR REPLACE(REPLACE(REPLACE(REPLACE(phone, ' ', ''), '-', ''), "
                "'(', ''), ')', '') LIKE ?"
            )
            params.append(f"%{phone_digits}%")
        return db.execute(
            f"""
            SELECT * FROM orders
            WHERE deleted_at IS NULL
              AND (customer_name LIKE ?
               OR phone LIKE ?
               OR email LIKE ?
               OR product_name LIKE ?
               OR product_model LIKE ?
               OR supplier LIKE ?
               OR notes LIKE ?{phone_clause})
            ORDER BY
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
        """
        SELECT * FROM orders
        WHERE deleted_at IS NULL
        ORDER BY
            CASE priority
                WHEN 'Brýnt' THEN 0
                WHEN 'Mikilvægt' THEN 1
                ELSE 2
            END,
            created_at DESC
        """
    ).fetchall()


def _board_version_for_rows(rows, query):
    count = len(rows)
    max_updated = max((r["updated_at"] for r in rows), default="")
    return f"{count}:{max_updated}:{query}"


@app.cli.command("init-db")
def init_db_command():
    """Create the database tables."""
    with app.app_context():
        init_db()
    print("Database initialized.")


# Auto-init on first request
with app.app_context():
    _conn = sqlite3.connect(DATABASE)
    _conn.executescript(
        """
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
        """
    )
    _conn.executescript(
        """
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
    )
    _conn.commit()
    _conn.close()

# ── Auth helpers ────────────────────────────────────────────────────


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def stjori_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        if session.get("role") != ROLE_STJORI:
            flash("Aðeins Stjóri hefur aðgang að þessu.", "error")
            return redirect(url_for("board"))
        return f(*args, **kwargs)

    return decorated


@app.context_processor
def inject_role():
    role = session.get("role")
    return {
        "role": role,
        "is_stjori": role == ROLE_STJORI,
        "is_notandi": role == ROLE_NOTANDI,
        "role_label": ROLE_LABELS.get(role, ""),
    }


def _digits_only(s):
    return "".join(c for c in (s or "") if c.isdigit())


def _phone_matches(query_digits, stored_phone):
    """Lightweight match: full digit equality or same last 7 digits (Iceland mobiles)."""
    db_digits = _digits_only(stored_phone)
    if not query_digits or not db_digits:
        return False
    if query_digits == db_digits:
        return True
    if len(query_digits) >= 7 and len(db_digits) >= 7:
        return query_digits[-7:] == db_digits[-7:]
    return query_digits == db_digits


def _smtp_config():
    return {
        "server": os.environ.get("SMTP_SERVER"),
        "port": int(os.environ.get("SMTP_PORT", 587)),
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASS"),
        "from": os.environ.get("SMTP_FROM", "no-reply@tolvuhvislarinn.is"),
        "shop_name": os.environ.get("SHOP_NAME", "Verslunin"),
    }


def _send_email(to_email, subject, body):
    cfg = _smtp_config()
    if not cfg["server"] or not cfg["user"] or not cfg["password"] or not to_email:
        return False
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = to_email
    try:
        server = smtplib.SMTP(cfg["server"], cfg["port"])
        server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def send_notification_email(to_email, order):
    cfg = _smtp_config()
    shop_name = cfg["shop_name"]
    status = order["status"]
    footer = f"---\nKeyrt af Muninn · https://muninn.tolvuhvislarinn.is"

    if status == "Staðfest":
        eta = order["estimated_arrival"] or ""
        eta_line = f"Áætluð koma: {eta}\n\n" if eta else ""
        body = (
            f"Sæl(l) {order['customer_name']},\n\n"
            f"Pöntun þín (#{order['id']} – {order['product_name']}) hefur verið "
            f"staðfest hjá birgi og er á leiðinni.\n\n"
            f"{eta_line}"
            f"Við látum þig vita þegar varan mætir.\n\n"
            f"Kveðja,\n{shop_name}\n\n"
            f"{footer}"
        )
        subject = f"Pöntun #{order['id']} staðfest – {shop_name}"

    elif status == "Komið":
        body = (
            f"Sæl(l) {order['customer_name']},\n\n"
            f"Varan þín er komin! "
            f"{order['product_name']} (pöntun #{order['id']}) "
            f"bíður þín hjá okkur.\n\n"
            f"Kveðja,\n{shop_name}\n\n"
            f"{footer}"
        )
        subject = f"Varan þín er komin – {shop_name}"

    else:
        track_url = f"{request.host_url.rstrip('/')}{url_for('track')}"
        body = (
            f"Sæl(l) {order['customer_name']},\n\n"
            f"Staða pöntunar þinnar (#{order['id']} – {order['product_name']}) "
            f"hefur verið uppfærð í: {status}.\n\n"
            f"Þú getur skoðað stöðu með símanúmerinu þínu hér: {track_url}\n\n"
            f"Kveðja,\n{shop_name}\n\n"
            f"{footer}"
        )
        subject = f"Uppfærsla á pöntun #{order['id']} – {shop_name}"

    threading.Thread(target=_send_email, args=(to_email, subject, body)).start()
    return True


# ── Routes: Auth ────────────────────────────────────────────────────


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        role = request.form.get("role", ROLE_NOTANDI)
        if role not in (ROLE_STJORI, ROLE_NOTANDI):
            role = ROLE_NOTANDI
        if check_password_hash(_password_hash_for_role(role), password):
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


# ── Routes: Public Tracking ──────────────────────────────────────────

@app.route("/track", methods=["GET", "POST"])
def track():
    """Public lookup: símanúmer → listi pantana (einfalt, án innskráningar)."""
    if request.method == "POST":
        raw_phone = request.form.get("phone", "").strip()
        qdigits = _digits_only(raw_phone)

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
            if r["deleted_at"] is None and _phone_matches(qdigits, r["phone"])
        ]

        if not orders:
            flash("Engar pantanir fundust fyrir þetta númer.", "error")

        return render_template(
            "track.html", orders=orders, track_url=track_public_url()
        )

    return render_template("track.html", orders=None, track_url=track_public_url())


# ── Routes: Board ───────────────────────────────────────────────────


@app.route("/")
@login_required
def board():
    db = get_db()
    query = request.args.get("q", "").strip()
    rows = _board_orders_query(db, query)

    today = datetime.now().strftime("%Y-%m-%d")
    columns = {s: [] for s in STATUSES}
    for row in rows:
        status = row["status"]
        if status in columns:
            columns[status].append(_order_card_view(row, today))

    board_version = _board_version_for_rows(rows, query)
    return render_template(
        "board.html",
        columns=columns,
        statuses=STATUSES,
        status_help=STATUS_HELP,
        query=query,
        today=today,
        board_version=board_version,
        trash_count=_trash_count(db),
    )


@app.route("/api/board/version")
@login_required
def board_version_api():
    db = get_db()
    query = request.args.get("q", "").strip()
    rows = _board_orders_query(db, query)
    return jsonify({"version": _board_version_for_rows(rows, query)})


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


# ── Routes: Create order ───────────────────────────────────────────


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


# ── Routes: View order detail ──────────────────────────────────────


@app.route("/order/<int:order_id>")
@login_required
def order_detail(order_id):
    db = get_db()
    order = _get_order(db, order_id)
    if order is None:
        abort(404)

    today = datetime.now().strftime("%Y-%m-%d")
    status_idx = STATUSES.index(order["status"]) if order["status"] in STATUSES else 0
    events = get_order_events(db, order_id)
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
    )


@app.route("/order/<int:order_id>/comments", methods=["POST"])
@login_required
def order_comment_add(order_id):
    body = request.form.get("body", "").strip()
    if not body:
        flash("Athugasemd má ekki vera tóm.", "error")
        return redirect(url_for("order_detail", order_id=order_id))

    db = get_db()
    order = _get_order(db, order_id)
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
    order = _get_order(db, order_id)
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


# ── Routes: Edit order ─────────────────────────────────────────────


@app.route("/order/<int:order_id>/edit", methods=["GET", "POST"])
@login_required
def order_edit(order_id):
    db = get_db()
    order = _get_order(db, order_id)
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
        
        send_notification = request.form.get("send_notification") == "1"
        if send_notification and order["status"] != request.form.get("status", order["status"]) and request.form.get("email", "").strip():
            updated_order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if send_notification_email(updated_order["email"], updated_order):
                flash("Pöntun uppfærð og tilkynning send.", "success")
            else:
                flash("Pöntun uppfærð en tókst ekki að senda tölvupóst.", "error")
            return redirect(url_for("board"))
            
        flash("Pöntun uppfærð.", "success")
        return redirect(url_for("board"))

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


# ── Routes: Delete order ───────────────────────────────────────────


@app.route("/order/<int:order_id>/delete", methods=["POST"])
@login_required
@stjori_required
def order_delete(order_id):
    db = get_db()
    order = _get_order(db, order_id)
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
        "UPDATE orders SET deleted_at = NULL, updated_at = ? WHERE id = ?",
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
    _hard_delete_order(db, order_id)
    flash("Pöntun eytt varanlega.", "success")
    return redirect(url_for("trash"))


# ── Routes: Quick status change ────────────────────────────────────


@app.route("/order/<int:order_id>/status", methods=["POST"])
@login_required
def order_status(order_id):
    new_status = request.form.get("status", "")
    if new_status not in STATUSES:
        abort(400)

    db = get_db()
    order = _get_order(db, order_id)
    if order is None:
        abort(404)

    if session.get("role") == ROLE_NOTANDI:
        status_idx = (
            STATUSES.index(order["status"]) if order["status"] in STATUSES else 0
        )
        next_status = (
            STATUSES[status_idx + 1] if status_idx < len(STATUSES) - 1 else None
        )
        if new_status != next_status:
            flash("Notandi getur aðeins fært pöntun áfram um eitt skref.", "error")
            return redirect(url_for("order_detail", order_id=order_id))

    now = datetime.now().isoformat(timespec="seconds")
    extra_updates = ""
    params = [new_status, now]

    if new_status == "Lokið" and not order["date_completed"]:
        extra_updates = ", date_completed=?"
        params.append(datetime.now().strftime("%Y-%m-%d"))

    params.append(order_id)
    if order["status"] != new_status:
        log_order_event(db, order_id, "status", order["status"], new_status)
    db.execute(
        f"UPDATE orders SET status=?, updated_at=?{extra_updates} WHERE id=?",
        params,
    )
    db.commit()

    auto_notify = new_status in ("Komið", "Staðfest")
    if (request.form.get("send_notification") == "1" or auto_notify) and order["status"] != new_status and (order["email"] or "").strip():
        updated_order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        send_notification_email(updated_order["email"], updated_order)
        flash("Staða uppfærð. Tilkynning send í bakgrunni.", "success")
    else:
        flash("Staða uppfærð.", "success")

    return redirect(url_for("order_detail", order_id=order_id))


# ── Routes: Quick contact-status change ────────────────────────────


@app.route("/order/<int:order_id>/contact_status", methods=["POST"])
@login_required
def order_contact_status(order_id):
    new_value = request.form.get("contact_status", "")
    if new_value not in CONTACT_OPTIONS:
        abort(400)

    db = get_db()
    db_order = _get_order(db, order_id)
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


# ── Routes: Attachments ────────────────────────────────────────────


def _allowed(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _order_upload_dir(order_id: int) -> str:
    path = os.path.join(UPLOAD_ROOT, str(order_id))
    os.makedirs(path, exist_ok=True)
    return path


def _hard_delete_order(db, order_id):
    db.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    db.commit()
    upload_dir = _order_upload_dir(order_id)
    if os.path.isdir(upload_dir):
        shutil.rmtree(upload_dir, ignore_errors=True)


def _attachment_payload(row, order_id):
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


@app.route("/order/<int:order_id>/attachments", methods=["GET"])
@login_required
def attachment_list(order_id):
    db = get_db()
    if _get_order(db, order_id) is None:
        abort(404)
    rows = db.execute(
        "SELECT * FROM attachments WHERE order_id = ? ORDER BY uploaded_at DESC, id DESC",
        (order_id,),
    ).fetchall()
    return jsonify([_attachment_payload(r, order_id) for r in rows])


@app.route("/order/<int:order_id>/attachments", methods=["POST"])
@login_required
def attachment_upload(order_id):
    db = get_db()
    if _get_order(db, order_id) is None:
        abort(404)

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "Engar skrár sendar."}), 400

    target_dir = _order_upload_dir(order_id)
    now = datetime.now().isoformat(timespec="seconds")
    saved, rejected = [], []

    for fs in files:
        original = fs.filename or ""
        if not _allowed(original):
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
        saved.append(_attachment_payload(row, order_id))

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
        _order_upload_dir(order_id),
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

    file_path = os.path.join(_order_upload_dir(order_id), row["stored_name"])
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


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "Skrá er of stór, hámark 25 MB."}), 413


# ── Run ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    if debug:
        app.run(host=host, port=port, debug=True)
    else:
        from waitress import serve

        print(f"Pantanakerfi running on http://{host}:{port}")
        serve(app, host=host, port=port, threads=4)
