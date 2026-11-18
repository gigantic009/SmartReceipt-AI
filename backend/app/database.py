"""SQLite persistence with explicit user ownership and auditable receipt review.

Legacy receipt rows are migrated with user_id=NULL and are never assigned to a
new account automatically. They remain inaccessible through user-facing APIs.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.app.auth import hash_password, new_session_token, token_digest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "backend" / "data" / "receipts.sqlite3"
SESSION_DAYS = 7

@contextmanager
def _connect(database_path: str | Path = DEFAULT_DATABASE_PATH):
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def initialize_database(database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS auth_attempts (
                attempt_key TEXT PRIMARY KEY,
                window_started_at TEXT NOT NULL,
                failures INTEGER NOT NULL DEFAULT 0,
                blocked_until TEXT
            );
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
            );
        """)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(receipts)")}
        if "user_id" not in columns:
            connection.execute("ALTER TABLE receipts ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
        connection.executescript("""
            CREATE INDEX IF NOT EXISTS idx_receipts_created_at ON receipts(created_at);
            CREATE INDEX IF NOT EXISTS idx_receipts_user_created ON receipts(user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_sessions_user_expiry ON sessions(user_id, expires_at);
            CREATE TABLE IF NOT EXISTS receipt_review_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id TEXT NOT NULL REFERENCES receipts(receipt_id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                previous_status TEXT NOT NULL,
                new_status TEXT NOT NULL,
                changes_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)

def create_user(name: str, email: str, password: str,
                database_path: str | Path = DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    initialize_database(database_path)
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect(database_path) as connection:
        cursor = connection.execute(
            "INSERT INTO users(name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name, email.lower(), hash_password(password), created_at))
        return {"id": cursor.lastrowid, "name": name, "email": email.lower()}

def find_user_by_email(email: str, database_path: str | Path = DEFAULT_DATABASE_PATH):
    initialize_database(database_path)
    with _connect(database_path) as connection:
        row = connection.execute("SELECT id, name, email, password_hash FROM users WHERE email = ?",
                                 (email.lower(),)).fetchone()
        return dict(row) if row else None

def create_session(user_id: int, database_path: str | Path = DEFAULT_DATABASE_PATH) -> str:
    initialize_database(database_path)
    token = new_session_token()
    now = datetime.now(timezone.utc)
    with _connect(database_path) as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now.isoformat(),))
        connection.execute("INSERT INTO sessions(token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token_digest(token), user_id, (now + timedelta(days=SESSION_DAYS)).isoformat(), now.isoformat()))
    return token

def get_session_user(token: str | None, database_path: str | Path = DEFAULT_DATABASE_PATH):
    if not token:
        return None
    initialize_database(database_path)
    with _connect(database_path) as connection:
        row = connection.execute("""
            SELECT u.id, u.name, u.email FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ?
        """, (token_digest(token), datetime.now(timezone.utc).isoformat())).fetchone()
        return dict(row) if row else None

def revoke_session(token: str | None, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
    if not token:
        return
    initialize_database(database_path)
    with _connect(database_path) as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_digest(token),))

def auth_is_blocked(attempt_key: str, database_path: str | Path = DEFAULT_DATABASE_PATH) -> bool:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        row = connection.execute("SELECT blocked_until FROM auth_attempts WHERE attempt_key = ?",
                                 (attempt_key,)).fetchone()
    if not row or not row["blocked_until"]:
        return False
    try:
        return datetime.fromisoformat(row["blocked_until"]) > datetime.now(timezone.utc)
    except ValueError:
        return False

def record_auth_failure(attempt_key: str, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
    initialize_database(database_path)
    now = datetime.now(timezone.utc)
    with _connect(database_path) as connection:
        row = connection.execute("SELECT window_started_at, failures FROM auth_attempts WHERE attempt_key = ?",
                                 (attempt_key,)).fetchone()
        if not row or now - datetime.fromisoformat(row["window_started_at"]) > timedelta(minutes=15):
            connection.execute("""
                INSERT INTO auth_attempts(attempt_key, window_started_at, failures, blocked_until)
                VALUES (?, ?, 1, NULL)
                ON CONFLICT(attempt_key) DO UPDATE SET
                    window_started_at = excluded.window_started_at, failures = 1, blocked_until = NULL
            """, (attempt_key, now.isoformat()))
            return
        failures = row["failures"] + 1
        blocked = (now + timedelta(minutes=15)).isoformat() if failures >= 8 else None
        connection.execute("UPDATE auth_attempts SET failures = ?, blocked_until = ? WHERE attempt_key = ?",
                           (failures, blocked, attempt_key))

def clear_auth_failures(attempt_key: str, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        connection.execute("DELETE FROM auth_attempts WHERE attempt_key = ?", (attempt_key,))

def save_receipt(*, receipt_id: str, user_id: int | None, original_filename: str,
    processed_filename: str, status: str, ocr_text: str, receipt: dict[str, Any],
    validation: dict[str, Any], ocr: dict[str, Any],
    database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
    initialize_database(database_path)
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect(database_path) as connection:
        connection.execute("""
            INSERT INTO receipts(receipt_id, user_id, original_filename, processed_filename, status,
                ocr_text, receipt_json, validation_json, ocr_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (receipt_id, user_id, original_filename, processed_filename, status, ocr_text,
              json.dumps(receipt, ensure_ascii=False), json.dumps(validation, ensure_ascii=False),
              json.dumps(ocr, ensure_ascii=False), created_at))

def list_receipts(user_id: int, *, page: int = 1, page_size: int = 20, query: str | None = None,
                  database_path: str | Path = DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    initialize_database(database_path)
    page = max(1, page)
    page_size = max(1, min(50, page_size))
    where = "user_id = ?"
    params: list[Any] = [user_id]
    if query:
        where += " AND (ocr_text LIKE ? OR receipt_json LIKE ?)"
        params.extend([f"%{query[:100]}%", f"%{query[:100]}%"])
    with _connect(database_path) as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM receipts WHERE {where}", params).fetchone()[0]
        rows = connection.execute(f"""
            SELECT receipt_id, status, receipt_json, ocr_json, created_at
            FROM receipts WHERE {where}
            ORDER BY created_at DESC, receipt_id DESC LIMIT ? OFFSET ?
        """, [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"items": [{"receipt_id": row["receipt_id"], "status": row["status"],
        "receipt": json.loads(row["receipt_json"]), "ocr": json.loads(row["ocr_json"]),
        "created_at": row["created_at"]} for row in rows],
        "page": page, "page_size": page_size, "total": total,
        "pages": (total + page_size - 1) // page_size}

def get_receipt(receipt_id: str, user_id: int,
                database_path: str | Path = DEFAULT_DATABASE_PATH):
    initialize_database(database_path)
    with _connect(database_path) as connection:
        row = connection.execute("""
            SELECT receipt_id, original_filename, processed_filename, status, ocr_text,
                receipt_json, validation_json, ocr_json, created_at
            FROM receipts WHERE receipt_id = ? AND user_id = ?
        """, (receipt_id, user_id)).fetchone()
    if not row:
        return None
    result = dict(row)
    for field in ("receipt_json", "validation_json", "ocr_json"):
        result[field.removesuffix("_json")] = json.loads(result.pop(field))
    return result

def review_receipt(receipt_id: str, user_id: int, *, status: str, fields: dict[str, Any],
                   database_path: str | Path = DEFAULT_DATABASE_PATH):
    if status not in {"approved", "rejected"}:
        raise ValueError("Review status must be approved or rejected.")
    initialize_database(database_path)
    now = datetime.now(timezone.utc).isoformat()
    with _connect(database_path) as connection:
        row = connection.execute("SELECT status, receipt_json FROM receipts WHERE receipt_id = ? AND user_id = ?",
                                 (receipt_id, user_id)).fetchone()
        if not row:
            return None
        previous = row["status"]
        receipt = json.loads(row["receipt_json"])
        before = {key: receipt.get(key) for key in fields}
        receipt.update(fields)
        connection.execute("UPDATE receipts SET status = ?, receipt_json = ? WHERE receipt_id = ? AND user_id = ?",
                           (status, json.dumps(receipt, ensure_ascii=False), receipt_id, user_id))
        connection.execute("""
            INSERT INTO receipt_review_events(receipt_id, user_id, previous_status, new_status, changes_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (receipt_id, user_id, previous, status,
              json.dumps({"before": before, "after": fields}, ensure_ascii=False), now))
    return {"receipt_id": receipt_id, "status": status, "receipt": receipt}

def delete_receipt(receipt_id: str, user_id: int,
                   database_path: str | Path = DEFAULT_DATABASE_PATH):
    initialize_database(database_path)
    with _connect(database_path) as connection:
        row = connection.execute("SELECT original_filename, processed_filename FROM receipts WHERE receipt_id = ? AND user_id = ?",
                                 (receipt_id, user_id)).fetchone()
        if not row:
            return None
        connection.execute("DELETE FROM receipts WHERE receipt_id = ? AND user_id = ?", (receipt_id, user_id))
        return dict(row)


def list_review_events(receipt_id: str, user_id: int,
                       database_path: str | Path = DEFAULT_DATABASE_PATH) -> list[dict[str, Any]] | None:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        owned = connection.execute(
            "SELECT 1 FROM receipts WHERE receipt_id = ? AND user_id = ?",
            (receipt_id, user_id),
        ).fetchone()
        if not owned:
            return None
        rows = connection.execute("""
            SELECT previous_status, new_status, changes_json, created_at
            FROM receipt_review_events
            WHERE receipt_id = ? AND user_id = ?
            ORDER BY id ASC
        """, (receipt_id, user_id)).fetchall()
    return [{
        "previous_status": row["previous_status"],
        "new_status": row["new_status"],
        "changes": json.loads(row["changes_json"]),
        "created_at": row["created_at"],
    } for row in rows]


def list_reconciliation_receipts(user_id: int, *, limit: int = 500,
                                 database_path: str | Path = DEFAULT_DATABASE_PATH) -> list[dict[str, Any]]:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        rows = connection.execute("""
            SELECT receipt_id, status, receipt_json, created_at
            FROM receipts
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, max(1, min(500, limit)))).fetchall()
    return [{
        "receipt_id": row["receipt_id"],
        "status": row["status"],
        "receipt": json.loads(row["receipt_json"]),
        "created_at": row["created_at"],
    } for row in rows]


def list_sessions(user_id: int, database_path: str | Path = DEFAULT_DATABASE_PATH) -> list[dict[str, Any]]:
    initialize_database(database_path)
    now = datetime.now(timezone.utc).isoformat()
    with _connect(database_path) as connection:
        rows = connection.execute("""
            SELECT created_at, expires_at FROM sessions
            WHERE user_id = ? AND expires_at > ?
            ORDER BY created_at DESC
        """, (user_id, now)).fetchall()
    return [{"created_at": row["created_at"], "expires_at": row["expires_at"]} for row in rows]


def revoke_all_sessions(user_id: int, database_path: str | Path = DEFAULT_DATABASE_PATH) -> int:
    initialize_database(database_path)
    with _connect(database_path) as connection:
        cursor = connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        return cursor.rowcount
