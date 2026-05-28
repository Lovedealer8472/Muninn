#!/usr/bin/env python3
"""Create fictional demo orders for demo.tolvuhvislarinn.is."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

SEED_ORDERS = [
    {
        "customer_name": "Demo Jón",
        "phone": "555-0101",
        "email": "demo.jon@example.is",
        "product_name": "MacBook Air",
        "product_model": "M2",
        "supplier": "TL",
        "status": "Móttekið",
        "notes": "Dæmi — ný pöntun móttekin.",
    },
    {
        "customer_name": "Prufu Anna",
        "phone": "555-0102",
        "email": "prufa.anna@example.is",
        "product_name": "Þvottavél",
        "product_model": "Bosch Serie 4",
        "supplier": "ELKO",
        "status": "Í vinnslu",
        "notes": "Verið er að vinna úr pöntun.",
    },
    {
        "customer_name": "Sýnishorn Karl",
        "phone": "555-0103",
        "email": "",
        "product_name": "Viroc plata",
        "product_model": "12 mm",
        "supplier": "Byko",
        "status": "Pantað",
        "date_ordered": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
    },
    {
        "customer_name": "Test Guðrún",
        "phone": "555-0104",
        "email": "test.gudrun@example.is",
        "product_name": "Gravel hjól",
        "product_model": "Sensa",
        "supplier": "Berlin",
        "status": "Staðfest",
        "estimated_arrival": (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"),
        "date_ordered": (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d"),
    },
    {
        "customer_name": "Demo Siggi",
        "phone": "555-0105",
        "email": "demo.siggi@example.is",
        "product_name": "Frystikista",
        "product_model": "A++",
        "supplier": "HT",
        "status": "Komið",
        "date_arrived": datetime.now().strftime("%Y-%m-%d"),
    },
    {
        "customer_name": "Prufu Helga",
        "phone": "555-0106",
        "email": "prufa.helga@example.is",
        "product_name": "Lyklabox",
        "product_model": "20 stk",
        "supplier": "TL",
        "status": "Komið",
        "date_arrived": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
    },
    {
        "customer_name": "Sýnishorn Ómar",
        "phone": "555-0107",
        "email": "",
        "product_name": "Ryksuga",
        "product_model": "Dyson V11",
        "supplier": "",
        "status": "Lokið",
        "payment_status": "Greitt",
        "date_completed": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
    },
    {
        "customer_name": "Demo Birna",
        "phone": "555-0108",
        "email": "demo.birna@example.is",
        "product_name": "Parket",
        "product_model": "Eik",
        "supplier": "Parket",
        "status": "Staðfest",
        "priority": "Mikilvægt",
        "estimated_arrival": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"),
    },
]


def _schema_sql() -> str:
    import sys

    root = Path(__file__).resolve().parent.parent
    app_root = root / "app" if (root / "app" / "muninn").is_dir() else root
    sys.path.insert(0, str(app_root))
    from muninn.db import SCHEMA_SQL

    return SCHEMA_SQL


def seed(db_path: Path) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    conn.executescript(_schema_sql())
    conn.execute(
        "ALTER TABLE orders ADD COLUMN suppress_auto_email INTEGER NOT NULL DEFAULT 0"
    )

    for row in SEED_ORDERS:
        conn.execute(
            """
            INSERT INTO orders (
                customer_name, phone, email, product_name, product_model, supplier,
                status, date_requested, date_ordered, estimated_arrival,
                date_arrived, date_completed, payment_status, contact_status,
                priority, notes, created_at, updated_at, suppress_auto_email
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                row["customer_name"],
                row["phone"],
                row.get("email", ""),
                row["product_name"],
                row.get("product_model", ""),
                row.get("supplier", ""),
                row["status"],
                row.get("date_requested", ""),
                row.get("date_ordered", ""),
                row.get("estimated_arrival", ""),
                row.get("date_arrived", ""),
                row.get("date_completed", ""),
                row.get("payment_status", "Ógreitt"),
                row.get("contact_status", "Ekki haft samband"),
                row.get("priority", "Venjulegt"),
                row.get("notes", ""),
                now,
                now,
            ),
        )

    count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    conn.commit()
    conn.close()
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "db_path",
        nargs="?",
        default="pantanakerfi.db",
        help="SQLite database path (default: pantanakerfi.db)",
    )
    parser.add_argument(
        "--seed-copy",
        metavar="PATH",
        help="Also write a copy to PATH (for weekly reset)",
    )
    args = parser.parse_args()
    db_path = Path(args.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    count = seed(db_path)
    print(f"Seeded {count} demo orders -> {db_path}")

    if args.seed_copy:
        copy_path = Path(args.seed_copy)
        copy_path.parent.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copy2(db_path, copy_path)
        print(f"Seed copy -> {copy_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
