#!/usr/bin/env python3
"""Merge Muninn SQLite data from source into target (pan trial).

Copies orders + related rows from pantanakerfi.tolvuhvislarinn.is into
pan.tolvuhvislarinn.is. Remaps order IDs to avoid collisions; skips
orders that look like duplicates (same phone + product + customer).

Usage (on server):
  python3 merge_pantanakerfi_to_pan.py --dry-run
  python3 merge_pantanakerfi_to_pan.py
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SOURCE = Path("/opt/pantanakerfi/pantanakerfi.db")
TARGET = Path("/opt/pan-tolvuhvisl/pantanakerfi.db")
UPLOADS_SOURCE = Path("/opt/pantanakerfi/uploads")
UPLOADS_TARGET = Path("/opt/pan-tolvuhvisl/uploads")

ORDER_COLS = [
    "customer_name",
    "phone",
    "email",
    "product_name",
    "product_model",
    "supplier",
    "status",
    "date_requested",
    "date_ordered",
    "estimated_arrival",
    "date_arrived",
    "date_completed",
    "payment_status",
    "contact_status",
    "priority",
    "notes",
    "created_at",
    "updated_at",
    "deleted_at",
    "suppress_auto_email",
]


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def table_cols(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def ensure_schema(conn: sqlite3.Connection) -> None:
    cols = table_cols(conn, "orders")
    if "suppress_auto_email" not in cols:
        conn.execute(
            "ALTER TABLE orders ADD COLUMN suppress_auto_email INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()


def dup_key(row: sqlite3.Row) -> tuple:
    return (
        (row["phone"] or "").strip(),
        (row["customer_name"] or "").strip().lower(),
        (row["product_name"] or "").strip().lower(),
        (row["product_model"] or "").strip().lower(),
    )


def existing_keys(conn: sqlite3.Connection) -> set[tuple]:
    keys: set[tuple] = set()
    for row in conn.execute("SELECT phone, customer_name, product_name, product_model FROM orders"):
        keys.add(dup_key(row))
    return keys


def copy_attachments(
    src_conn: sqlite3.Connection,
    tgt_conn: sqlite3.Connection,
    id_map: dict[int, int],
    dry_run: bool,
) -> int:
    if "attachments" not in {r[0] for r in src_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
        return 0
    count = 0
    UPLOADS_TARGET.mkdir(parents=True, exist_ok=True)
    for row in src_conn.execute("SELECT * FROM attachments ORDER BY id"):
        new_oid = id_map.get(row["order_id"])
        if new_oid is None:
            continue
        src_file = UPLOADS_SOURCE / row["stored_name"]
        if not dry_run:
            tgt_conn.execute(
                """
                INSERT INTO attachments
                    (order_id, filename, stored_name, mime_type, size_bytes, uploaded_by, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_oid,
                    row["filename"],
                    row["stored_name"],
                    row["mime_type"],
                    row["size_bytes"],
                    row["uploaded_by"],
                    row["uploaded_at"],
                ),
            )
            if src_file.is_file():
                dest = UPLOADS_TARGET / row["stored_name"]
                if not dest.exists():
                    shutil.copy2(src_file, dest)
        count += 1
    return count


def copy_child_rows(
    src_conn: sqlite3.Connection,
    tgt_conn: sqlite3.Connection,
    table: str,
    id_map: dict[int, int],
    dry_run: bool,
) -> int:
    tables = {r[0] for r in src_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if table not in tables:
        return 0
    cols = [c for c in table_cols(src_conn, table) if c not in ("id",)]
    col_list = ", ".join(cols)
    placeholders = ", ".join("?" for _ in cols)
    count = 0
    for row in src_conn.execute(f"SELECT * FROM {table} ORDER BY id"):
        new_oid = id_map.get(row["order_id"])
        if new_oid is None:
            continue
        values = [new_oid if c == "order_id" else row[c] for c in cols]
        if not dry_run:
            tgt_conn.execute(
                f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
                values,
            )
        count += 1
    return count


def merge(source: Path, target: Path, dry_run: bool) -> int:
    if not source.is_file():
        print(f"Source missing: {source}", file=sys.stderr)
        return 1
    if not target.is_file():
        print(f"Target missing: {target}", file=sys.stderr)
        return 1

    src = connect(source)
    tgt = connect(target)
    ensure_schema(src)
    ensure_schema(tgt)

    tgt_keys = existing_keys(tgt)
    src_orders = list(src.execute("SELECT * FROM orders ORDER BY id"))
    tgt_cols = set(table_cols(tgt, "orders"))
    use_cols = [c for c in ORDER_COLS if c in tgt_cols]

    id_map: dict[int, int] = {}
    imported = 0
    skipped = 0

    for row in src_orders:
        key = dup_key(row)
        if key in tgt_keys:
            skipped += 1
            print(f"  skip duplicate order #{row['id']} {row['customer_name']} / {row['product_name']}")
            continue

        if not dry_run:
            placeholders = ", ".join("?" for _ in use_cols)
            col_list = ", ".join(use_cols)
            values = [row[c] if c in row.keys() else None for c in use_cols]
            cur = tgt.execute(
                f"INSERT INTO orders ({col_list}) VALUES ({placeholders})",
                values,
            )
            id_map[row["id"]] = cur.lastrowid
        else:
            max_id = tgt.execute("SELECT COALESCE(MAX(id), 0) FROM orders").fetchone()[0]
            id_map[row["id"]] = max_id + imported + 1

        tgt_keys.add(key)
        imported += 1
        print(f"  import order #{row['id']} -> #{id_map[row['id']]} {row['customer_name']} / {row['product_name']}")

    events = comments = attachments = 0
    if imported and not dry_run:
        events = copy_child_rows(src, tgt, "order_events", id_map, dry_run)
        comments = copy_child_rows(src, tgt, "order_comments", id_map, dry_run)
        attachments = copy_attachments(src, tgt, id_map, dry_run)
        tgt.commit()
    elif imported:
        events = sum(
            1
            for r in src.execute("SELECT order_id FROM order_events")
            if r[0] in id_map
        )
        comments = sum(
            1
            for r in src.execute("SELECT order_id FROM order_comments")
            if r[0] in id_map
        )
        if "attachments" in {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            attachments = sum(
                1 for r in src.execute("SELECT order_id FROM attachments") if r[0] in id_map
            )

    src.close()
    tgt.close()

    mode = "DRY RUN" if dry_run else "DONE"
    print(
        f"\n{mode}: imported {imported} orders, skipped {skipped} duplicates, "
        f"{events} events, {comments} comments, {attachments} attachments"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--target", type=Path, default=TARGET)
    args = parser.parse_args()

    if not args.dry_run:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = args.target.with_suffix(f".db.pre-merge-{ts}.bak")
        shutil.copy2(args.target, backup)
        print(f"Backup: {backup}")

    return merge(args.source, args.target, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
