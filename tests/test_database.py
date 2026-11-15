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

def test_receipt_library_search_update_duplicate_and_analytics(tmp_path):
    from backend.app.database import (
        list_receipts, update_receipt, get_receipt, find_duplicate, get_analytics
    )
    database_path = tmp_path / "library.sqlite3"
    save_receipt(
        receipt_id="library-001",
        original_filename="hotel.jpg",
        processed_filename="hotel.png",
        status="review_required",
        ocr_text="Hotel total 1200",
        receipt={"total": "1200"},
        validation={"overall_status": "review_required"},
        ocr={"average_confidence": 70},
        global_document={
            "merchant_name_candidate": "Sunrise Hotel",
            "issue_date_raw": "2026-10-16",
            "currency": {"currency_code": "INR"},
            "amounts": {"grand_total": {"value": "1200"}},
            "category": "Travel",
        },
        content_sha256="same-image-hash",
        database_path=database_path,
    )
    assert len(list_receipts(search="Sunrise", database_path=database_path)) == 1
    assert find_duplicate("same-image-hash", database_path=database_path)["receipt_id"] == "library-001"
    assert update_receipt("library-001", {"merchant_name": "Sunrise Grand Hotel", "category": "Travel"}, database_path)
    record = get_receipt("library-001", database_path)
    assert record["merchant_name"] == "Sunrise Grand Hotel"
    assert record["ocr_text"] == "Hotel total 1200"
    summary = get_analytics(database_path)
    assert summary["document_count"] == 1
    assert summary["spend_by_currency"]["INR"] == 1200.0
    assert summary["spend_by_category"]["Travel"] == 1200.0


def test_manual_expense_vendor_budget_and_combined_analytics(tmp_path):
    from backend.app.database import (
        create_expense, list_expenses, create_vendor, list_vendors,
        create_budget, list_budgets, get_analytics,
    )
    database_path = tmp_path / "finance.sqlite3"
    create_expense({
        "description": "Metro ticket", "amount": "75.50", "currency_code": "INR",
        "expense_date": "2026-11-16", "category": "Travel",
    }, database_path)
    assert len(list_expenses(currency_code="INR", database_path=database_path)) == 1
    vendor = create_vendor({"name": "City Metro", "default_category": "Travel"}, database_path)
    assert vendor["name"] == "City Metro"
    assert list_vendors(database_path)[0]["vendor_id"] == vendor["vendor_id"]
    budget = create_budget({
        "name": "Monthly travel", "amount": "2500", "currency_code": "INR",
        "category": "Travel",
    }, database_path)
    assert list_budgets(database_path)[0]["budget_id"] == budget["budget_id"]
    analytics = get_analytics(database_path)
    assert analytics["expense_count"] == 1
    assert analytics["spend_by_currency"]["INR"] == 75.5


def test_receipt_correction_creates_audit_event(tmp_path):
    from backend.app.database import add_receipt_event, get_receipt_events
    database_path = tmp_path / "audit.sqlite3"
    add_receipt_event("receipt-42", "fields_corrected", {"category": "Travel"}, database_path)
    events = get_receipt_events("receipt-42", database_path)
    assert events[0]["action"] == "fields_corrected"
    assert events[0]["details"]["category"] == "Travel"
