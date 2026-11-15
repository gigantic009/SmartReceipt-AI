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
        connection.execute("""
            CREATE TABLE IF NOT EXISTS receipt_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                expense_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                merchant_name TEXT,
                amount TEXT NOT NULL,
                currency_code TEXT NOT NULL,
                expense_date TEXT,
                category TEXT NOT NULL DEFAULT 'Uncategorized',
                payment_method TEXT,
                receipt_id TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS vendors (
                vendor_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                default_category TEXT,
                tax_identifier TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                budget_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                amount TEXT NOT NULL,
                currency_code TEXT NOT NULL,
                period TEXT NOT NULL DEFAULT 'monthly',
                starts_on TEXT,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_receipt_events_receipt ON receipt_events(receipt_id, created_at)")
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
            document.get("merchant_name_candidate"), (document.get("issue_date") or {}).get("value") or document.get("issue_date_raw"),
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
    with _connect(database_path) as connection:
        row = connection.execute(
            "SELECT global_json FROM receipts WHERE receipt_id = ?", (receipt_id,)
        ).fetchone()
        if row is None:
            return False
        try:
            global_document = json.loads(row["global_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            global_document = {}
        for key, value in updates.items():
            if key == "merchant_name":
                global_document["merchant_name_candidate"] = value
            elif key == "document_date":
                global_document["issue_date_raw"] = value
            elif key == "currency_code":
                global_document.setdefault("currency", {})["currency_code"] = value
            elif key == "category":
                global_document["category"] = value
        updates["global_json"] = json.dumps(global_document, ensure_ascii=False)
        assignments = ", ".join(f"{key} = ?" for key in updates)
        cursor = connection.execute(
            f"UPDATE receipts SET {assignments} WHERE receipt_id = ?",
            (*updates.values(), receipt_id),
        )
        connection.commit()
        return cursor.rowcount > 0


def delete_receipt(receipt_id: str, database_path: str | Path = DEFAULT_DATABASE_PATH) -> bool:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        connection.execute("DELETE FROM receipt_events WHERE receipt_id = ?", (receipt_id,))
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
    """Combine saved-document and manually entered expenses without double counting."""
    initialize_database(database_path)
    with _connect(database_path) as connection:
        receipts = connection.execute(
            "SELECT total_amount, currency_code, category, status, document_date, created_at FROM receipts"
        ).fetchall()
        expenses = connection.execute(
            "SELECT amount, currency_code, category, expense_date, created_at FROM expenses WHERE receipt_id IS NULL"
        ).fetchall()
    totals: dict[str, float] = {}
    categories: dict[str, float] = {}
    monthly: dict[str, float] = {}

    def accumulate(amount_value, currency_value, category_value, date_value):
        try:
            amount = float(amount_value) if amount_value is not None else 0.0
        except (TypeError, ValueError):
            amount = 0.0
        currency = currency_value or "UNRESOLVED"
        totals[currency] = round(totals.get(currency, 0.0) + amount, 2)
        category = category_value or "Uncategorized"
        categories[category] = round(categories.get(category, 0.0) + amount, 2)
        period = (date_value or "")[:7] or "Unknown"
        monthly[period] = round(monthly.get(period, 0.0) + amount, 2)

    for row in receipts:
        accumulate(row["total_amount"], row["currency_code"], row["category"],
                   row["document_date"] or row["created_at"])
    for row in expenses:
        accumulate(row["amount"], row["currency_code"], row["category"],
                   row["expense_date"] or row["created_at"])
    return {
        "document_count": len(receipts),
        "expense_count": len(expenses),
        "review_required": sum(1 for row in receipts if row["status"] == "review_required"),
        "spend_by_currency": totals,
        "spend_by_category": categories,
        "monthly_spend": dict(sorted(monthly.items())),
    }

def add_receipt_event(receipt_id: str, action: str, details: dict[str, Any],
                      database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        connection.execute(
            "INSERT INTO receipt_events (receipt_id, action, details_json, created_at) VALUES (?, ?, ?, ?)",
            (receipt_id, action, json.dumps(details, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
        )
        connection.commit()


def get_receipt_events(receipt_id: str, database_path: str | Path = DEFAULT_DATABASE_PATH) -> list[dict]:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM receipt_events WHERE receipt_id = ? ORDER BY created_at DESC",
            (receipt_id,),
        ).fetchall()
    return [{**dict(row), "details": json.loads(row["details_json"] or "{}")} for row in rows]


def create_expense(data: dict[str, Any], database_path: str | Path = DEFAULT_DATABASE_PATH) -> dict:
    initialize_database(database_path)
    expense_id = data.get("expense_id") or __import__("uuid").uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    fields = {
        "expense_id": expense_id,
        "description": str(data["description"]).strip(),
        "merchant_name": data.get("merchant_name"),
        "amount": str(data["amount"]),
        "currency_code": str(data["currency_code"]).upper(),
        "expense_date": data.get("expense_date"),
        "category": data.get("category") or "Uncategorized",
        "payment_method": data.get("payment_method"),
        "receipt_id": data.get("receipt_id"),
        "notes": data.get("notes"),
        "created_at": created_at,
    }
    with _connect(database_path) as connection:
        connection.execute(
            """INSERT INTO expenses (expense_id, description, merchant_name, amount,
            currency_code, expense_date, category, payment_method, receipt_id, notes, created_at)
            VALUES (:expense_id, :description, :merchant_name, :amount, :currency_code,
            :expense_date, :category, :payment_method, :receipt_id, :notes, :created_at)""",
            fields,
        )
        connection.commit()
    return fields


def list_expenses(currency_code: str | None = None, category: str | None = None,
                  database_path: str | Path = DEFAULT_DATABASE_PATH) -> list[dict]:
    initialize_database(database_path)
    clauses, values = [], []
    if currency_code:
        clauses.append("currency_code = ?"); values.append(currency_code.upper())
    if category:
        clauses.append("category = ?"); values.append(category)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _connect(database_path) as connection:
        rows = connection.execute(f"SELECT * FROM expenses{where} ORDER BY expense_date DESC, created_at DESC", values).fetchall()
    return [dict(row) for row in rows]


def delete_expense(expense_id: str, database_path: str | Path = DEFAULT_DATABASE_PATH) -> bool:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        cursor = connection.execute("DELETE FROM expenses WHERE expense_id = ?", (expense_id,))
        connection.commit()
        return cursor.rowcount > 0


def create_vendor(data: dict[str, Any], database_path: str | Path = DEFAULT_DATABASE_PATH) -> dict:
    initialize_database(database_path)
    vendor_id = __import__("uuid").uuid4().hex
    record = {"vendor_id": vendor_id, "name": str(data["name"]).strip(),
              "default_category": data.get("default_category"),
              "tax_identifier": data.get("tax_identifier"), "notes": data.get("notes"),
              "created_at": datetime.now(timezone.utc).isoformat()}
    with _connect(database_path) as connection:
        connection.execute(
            "INSERT INTO vendors (vendor_id, name, default_category, tax_identifier, notes, created_at) VALUES (:vendor_id, :name, :default_category, :tax_identifier, :notes, :created_at)",
            record,
        )
        connection.commit()
    return record


def list_vendors(database_path: str | Path = DEFAULT_DATABASE_PATH) -> list[dict]:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM vendors ORDER BY name").fetchall()]


def create_budget(data: dict[str, Any], database_path: str | Path = DEFAULT_DATABASE_PATH) -> dict:
    initialize_database(database_path)
    budget_id = __import__("uuid").uuid4().hex
    record = {"budget_id": budget_id, "name": str(data["name"]).strip(),
              "category": data.get("category"), "amount": str(data["amount"]),
              "currency_code": str(data["currency_code"]).upper(),
              "period": data.get("period", "monthly"), "starts_on": data.get("starts_on"),
              "created_at": datetime.now(timezone.utc).isoformat()}
    with _connect(database_path) as connection:
        connection.execute(
            "INSERT INTO budgets (budget_id, name, category, amount, currency_code, period, starts_on, created_at) VALUES (:budget_id, :name, :category, :amount, :currency_code, :period, :starts_on, :created_at)",
            record,
        )
        connection.commit()
    return record


def list_budgets(database_path: str | Path = DEFAULT_DATABASE_PATH) -> list[dict]:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM budgets ORDER BY created_at DESC").fetchall()]

def get_budget_status(as_of=None, database_path: str | Path = DEFAULT_DATABASE_PATH) -> list[dict]:
    """Calculate budget consumption in the same currency without FX assumptions."""
    from datetime import date, timedelta
    from decimal import Decimal, InvalidOperation
    today = as_of or date.today()
    initialize_database(database_path)
    with _connect(database_path) as connection:
        budgets = connection.execute("SELECT * FROM budgets ORDER BY created_at DESC").fetchall()
        receipts = connection.execute(
            "SELECT total_amount, currency_code, category, document_date, created_at FROM receipts"
        ).fetchall()
        expenses = connection.execute(
            "SELECT amount, currency_code, category, expense_date, created_at FROM expenses WHERE receipt_id IS NULL"
        ).fetchall()

    def period_start(period):
        if period == "weekly":
            return today - timedelta(days=today.weekday())
        if period == "quarterly":
            month = ((today.month - 1) // 3) * 3 + 1
            return date(today.year, month, 1)
        if period == "yearly":
            return date(today.year, 1, 1)
        return date(today.year, today.month, 1)

    results = []
    for budget in budgets:
        start = period_start(budget["period"])
        if budget["starts_on"]:
            try:
                start = max(start, date.fromisoformat(budget["starts_on"]))
            except ValueError:
                pass
        spent = Decimal("0")
        for row, amount_key, date_key in (
            *((row, "total_amount", "document_date") for row in receipts),
            *((row, "amount", "expense_date") for row in expenses),
        ):
            if row["currency_code"] != budget["currency_code"]:
                continue
            if budget["category"] and row["category"] != budget["category"]:
                continue
            try:
                amount = Decimal(str(row[amount_key] or "0"))
                raw_date = row[date_key] or row["created_at"]
                entry_date = date.fromisoformat(str(raw_date)[:10])
            except (InvalidOperation, ValueError, TypeError):
                continue
            if start <= entry_date <= today:
                spent += amount
        try:
            limit = Decimal(budget["amount"])
        except InvalidOperation:
            limit = Decimal("0")
        remaining = limit - spent
        utilization = (spent / limit * 100) if limit > 0 else None
        results.append({
            **dict(budget),
            "period_start": start.isoformat(),
            "as_of": today.isoformat(),
            "spent": format(spent, "f"),
            "remaining": format(remaining, "f"),
            "utilization_percent": round(float(utilization), 2) if utilization is not None else None,
            "status": "over_budget" if spent > limit else "near_limit" if utilization is not None and utilization >= 80 else "within_budget",
        })
    return results

