"""SQLite persistence for processed receipt records.

The database is local application data. Do not commit it or store real receipt
data in a public repository. Production deployment requires authentication,
authorization, retention controls, and encrypted storage.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "backend" / "data" / "receipts.sqlite3"


def initialize_database(database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
    """Create the receipt table and indexes if they do not already exist."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        connection.execute(
            """
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
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_receipts_created_at ON receipts(created_at)"
        )
        connection.commit()


def save_receipt(
    *,
    receipt_id: str,
    original_filename: str,
    processed_filename: str,
    status: str,
    ocr_text: str,
    receipt: dict[str, Any],
    validation: dict[str, Any],
    ocr: dict[str, Any],
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> None:
    """Persist one completed receipt result using a parameterized SQL query."""
    initialize_database(database_path)
    created_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(database_path, timeout=10) as connection:
        connection.execute(
            """
            INSERT INTO receipts (
                receipt_id, original_filename, processed_filename, status,
                ocr_text, receipt_json, validation_json, ocr_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                original_filename,
                processed_filename,
                status,
                ocr_text,
                json.dumps(receipt, ensure_ascii=False),
                json.dumps(validation, ensure_ascii=False),
                json.dumps(ocr, ensure_ascii=False),
                created_at,
            ),
        )
        connection.commit()
