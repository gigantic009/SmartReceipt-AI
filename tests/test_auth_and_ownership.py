import sqlite3

from backend.app.auth import hash_password, token_digest, verify_password
from backend.app.database import (
    create_session, create_user, get_session_user, initialize_database,
    list_receipts, review_receipt, save_receipt,
)


def test_scrypt_password_hash_and_opaque_session(tmp_path):
    path = tmp_path / "secure.sqlite3"
    user = create_user("A User", "a@example.com", "correct horse battery", path)
    assert verify_password("correct horse battery", hash_password_for_user(path, "a@example.com"))
    assert not verify_password("wrong password", hash_password_for_user(path, "a@example.com"))
    token = create_session(user["id"], path)
    assert get_session_user(token, path)["id"] == user["id"]
    with sqlite3.connect(path) as connection:
        stored_hash = connection.execute("SELECT token_hash FROM sessions").fetchone()[0]
    assert stored_hash == token_digest(token)
    assert stored_hash != token


def hash_password_for_user(path, email):
    import sqlite3
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()[0]


def test_receipt_rows_are_isolated_and_review_is_audited(tmp_path):
    path = tmp_path / "receipts.sqlite3"
    owner = create_user("Owner", "owner@example.com", "owner-password-123", path)
    other = create_user("Other", "other@example.com", "other-password-123", path)
    save_receipt(
        receipt_id="receipt-owned", user_id=owner["id"],
        original_filename="original.jpg", processed_filename="processed.png",
        status="review_required", ocr_text="Merchant Example Total 125.00",
        receipt={"merchant": "Merchant Example", "total": "125.00"},
        validation={"overall_status": "review_required"},
        ocr={"average_confidence": 72.0}, database_path=path,
    )
    assert list_receipts(owner["id"], database_path=path)["total"] == 1
    assert list_receipts(other["id"], database_path=path)["total"] == 0
    assert review_receipt("receipt-owned", other["id"], status="approved", fields={}, database_path=path) is None
    reviewed = review_receipt(
        "receipt-owned", owner["id"], status="approved",
        fields={"total": "125.50"}, database_path=path,
    )
    assert reviewed["receipt"]["total"] == "125.50"
    with sqlite3.connect(path) as connection:
        event = connection.execute(
            "SELECT previous_status, new_status, changes_json FROM receipt_review_events"
        ).fetchone()
    assert event[0] == "review_required"
    assert event[1] == "approved"
    assert '"125.50"' in event[2]


def test_legacy_receipts_are_not_assigned_to_new_users(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("""
            CREATE TABLE receipts (
                receipt_id TEXT PRIMARY KEY, original_filename TEXT NOT NULL,
                processed_filename TEXT NOT NULL, status TEXT NOT NULL,
                ocr_text TEXT NOT NULL, receipt_json TEXT NOT NULL,
                validation_json TEXT NOT NULL, ocr_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute(
            "INSERT INTO receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("legacy", "old.jpg", "old.png", "success", "OCR", "{}", "{}", "{}", "2026-01-01T00:00:00+00:00"),
        )
    initialize_database(path)
    new_user = create_user("New user", "new@example.com", "long-password-123", path)
    assert list_receipts(new_user["id"], database_path=path)["total"] == 0
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT user_id FROM receipts WHERE receipt_id = 'legacy'").fetchone()
    assert row[0] is None
