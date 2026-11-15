"""SQLite persistence and query services for SmartReceipt AI.

Local prototype storage only. Production use requires authentication,
authorization, encryption, retention controls and per-user isolation.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "backend" / "data" / "receipts.sqlite3"


def _connect(database_path: str | Path = DEFAULT_DATABASE_PATH):
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
    with _connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id TEXT PRIMARY KEY,
                original_filename TEXT NOT NULL,
                processed_filename TEXT NOT NULL,
                status TEXT NOT NULL,
                ocr_text TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                validation_json TEXT NOT NULL,
                ocr_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(receipts)")}
        migrations = {
            "global_json": "TEXT NOT NULL DEFAULT '{}'",
            "content_sha256": "TEXT",
            "merchant_name": "TEXT",
            "document_date": "TEXT",
            "total_amount": "TEXT",
            "currency_code": "TEXT",
            "category": "TEXT",
            "review_notes": "TEXT",
            "updated_at": "TEXT",
        }
        for name, declaration in migrations.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE receipts ADD COLUMN {name} {declaration}")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_receipts_created_at ON receipts(created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_receipts_sha256 ON receipts(content_sha256)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_receipts_merchant ON receipts(merchant_name)")
        connection.commit()


def save_receipt(*, receipt_id: str, original_filename: str, processed_filename: str,
                 status: str, ocr_text: str, receipt: dict[str, Any],
                 validation: dict[str, Any], ocr: dict[str, Any],
                 global_document: dict[str, Any] | None = None,
                 content_sha256: str | None = None,
                 database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
    initialize_database(database_path)
    created_at = datetime.now(timezone.utc).isoformat()
    document = global_document or {}
    amounts = document.get("amounts", {})
    total = amounts.get("grand_total") or {}
    if isinstance(total, dict):
        total = total.get("value")
    with _connect(database_path) as connection:
        connection.execute("""
            INSERT INTO receipts (
                receipt_id, original_filename, processed_filename, status, ocr_text,
                receipt_json, validation_json, ocr_json, created_at, global_json,
                content_sha256, merchant_name, document_date, total_amount,
                currency_code, category, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            receipt_id, original_filename, processed_filename, status, ocr_text,
            json.dumps(receipt, ensure_ascii=False),
            json.dumps(validation, ensure_ascii=False),
            json.dumps(ocr, ensure_ascii=False), created_at,
            json.dumps(document, ensure_ascii=False), content_sha256,
            document.get("merchant_name_candidate"), document.get("issue_date_raw"),
            str(total) if total is not None else None,
            document.get("currency", {}).get("currency_code"),
            document.get("category"),
            created_at,
        ))
        connection.commit()


def _record(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    for column, target in (
        ("receipt_json", "receipt"), ("validation_json", "validation"),
        ("ocr_json", "ocr"), ("global_json", "global"),
    ):
        raw = item.pop(column, "{}")
        try:
            item[target] = json.loads(raw or "{}")
        except (TypeError, json.JSONDecodeError):
            item[target] = {}
    item.pop("ocr_text", None)
    return item


def list_receipts(*, search: str | None = None, status: str | None = None,
                  category: str | None = None, limit: int = 100, offset: int = 0,
                  database_path: str | Path = DEFAULT_DATABASE_PATH) -> list[dict[str, Any]]:
    initialize_database(database_path)
    clauses, values = [], []
    if search:
        clauses.append("(merchant_name LIKE ? OR original_filename LIKE ? OR receipt_id LIKE ?)")
        values.extend([f"%{search}%"] * 3)
    if status:
        clauses.append("status = ?"); values.append(status)
    if category:
        clauses.append("category = ?"); values.append(category)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _connect(database_path) as connection:
        rows = connection.execute(
            f"SELECT * FROM receipts{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*values, max(1, min(limit, 500)), max(0, offset)),
        ).fetchall()
    return [_record(row) for row in rows]


def get_receipt(receipt_id: str, database_path: str | Path = DEFAULT_DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        row = connection.execute("SELECT * FROM receipts WHERE receipt_id = ?", (receipt_id,)).fetchone()
    if row is None:
        return None
    item = _record(row)
    with _connect(database_path) as connection:
        full = connection.execute("SELECT ocr_text FROM receipts WHERE receipt_id = ?", (receipt_id,)).fetchone()
    item["ocr_text"] = full["ocr_text"] if full else ""
    return item


def update_receipt(receipt_id: str, fields: dict[str, Any],
                   database_path: str | Path = DEFAULT_DATABASE_PATH) -> bool:
    allowed = {"merchant_name", "document_date", "total_amount", "currency_code", "category", "review_notes", "status"}
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return False
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    initialize_database(database_path)
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with _connect(database_path) as connection:
        cursor = connection.execute(
            f"UPDATE receipts SET {assignments} WHERE receipt_id = ?",
            (*updates.values(), receipt_id),
        )
        connection.commit()
        return cursor.rowcount > 0


def delete_receipt(receipt_id: str, database_path: str | Path = DEFAULT_DATABASE_PATH) -> bool:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        cursor = connection.execute("DELETE FROM receipts WHERE receipt_id = ?", (receipt_id,))
        connection.commit()
        return cursor.rowcount > 0


def find_duplicate(content_sha256: str, database_path: str | Path = DEFAULT_DATABASE_PATH) -> dict[str, Any] | None:
    if not content_sha256:
        return None
    initialize_database(database_path)
    with _connect(database_path) as connection:
        row = connection.execute(
            "SELECT receipt_id, original_filename, created_at FROM receipts WHERE content_sha256 = ? ORDER BY created_at DESC LIMIT 1",
            (content_sha256,),
        ).fetchone()
    return dict(row) if row else None


def get_analytics(database_path: str | Path = DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        rows = connection.execute(
            "SELECT total_amount, currency_code, category, status, document_date, created_at FROM receipts"
        ).fetchall()
    totals: dict[str, float] = {}
    categories: dict[str, float] = {}
    monthly: dict[str, float] = {}
    for row in rows:
        try:
            amount = float(row["total_amount"]) if row["total_amount"] is not None else 0.0
        except (TypeError, ValueError):
            amount = 0.0
        currency = row["currency_code"] or "UNRESOLVED"
        totals[currency] = round(totals.get(currency, 0.0) + amount, 2)
        category = row["category"] or "Uncategorized"
        categories[category] = round(categories.get(category, 0.0) + amount, 2)
        period = (row["document_date"] or row["created_at"] or "")[:7] or "Unknown"
        monthly[period] = round(monthly.get(period, 0.0) + amount, 2)
    return {
        "document_count": len(rows),
        "review_required": sum(1 for row in rows if row["status"] == "review_required"),
        "spend_by_currency": totals,
        "spend_by_category": categories,
        "monthly_spend": dict(sorted(monthly.items())),
    }
