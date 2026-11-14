import json
import sqlite3

from backend.app.database import save_receipt


def test_save_receipt_persists_structured_result(tmp_path):
    database_path = tmp_path / "data" / "receipts.sqlite3"

    save_receipt(
        receipt_id="receipt-test-001",
        original_filename="receipt-test-001.jpg",
        processed_filename="receipt-test-001.png",
        status="review_required",
        ocr_text="Total 100.00",
        receipt={"total": "100.00", "raw_amounts": {"total": "100.00"}},
        validation={"overall_status": "review_required"},
        ocr={"average_confidence": 72.5, "review_required": True},
        database_path=database_path,
    )

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT receipt_id, status, ocr_text, receipt_json,
                   validation_json, ocr_json, created_at
            FROM receipts WHERE receipt_id = ?
            """,
            ("receipt-test-001",),
        ).fetchone()

    assert row is not None
    assert row[0] == "receipt-test-001"
    assert row[1] == "review_required"
    assert row[2] == "Total 100.00"
    assert json.loads(row[3])["total"] == "100.00"
    assert json.loads(row[4])["overall_status"] == "review_required"
    assert json.loads(row[5])["average_confidence"] == 72.5
    assert row[6]


def test_save_receipt_rejects_duplicate_ids(tmp_path):
    database_path = tmp_path / "receipts.sqlite3"
    values = {
        "receipt_id": "duplicate-id",
        "original_filename": "original.jpg",
        "processed_filename": "processed.png",
        "status": "review_required",
        "ocr_text": "OCR",
        "receipt": {},
        "validation": {},
        "ocr": {},
        "database_path": database_path,
    }
    save_receipt(**values)

    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        save_receipt(**values)
