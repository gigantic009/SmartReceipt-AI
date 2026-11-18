from evaluation.metrics import evaluate_records
from backend.app.reconciliation import suggest_matches


def test_evaluation_reports_field_level_accuracy_and_numeric_error():
    records = [
        {"ocr_text": "receipt one", "expected": {"merchant": "Example Mart", "total": "100.00"}},
        {"ocr_text": "receipt two", "expected": {"merchant": "Other Shop", "total": "90.00"}},
    ]
    def parser(text):
        return {"merchant": "Example Mart" if text == "receipt one" else "Other Shop",
                "total": "100.00" if text == "receipt one" else "91.00"}
    result = evaluate_records(records, parser)
    assert result["record_count"] == 2
    assert result["fields"]["merchant"]["exact_match_rate"] == 1.0
    assert result["fields"]["total"]["mean_absolute_error"] == 0.5


def test_reconciliation_is_explainable_and_never_auto_confirms():
    receipts = [{
        "receipt_id": "r-1", "status": "review_required",
        "receipt": {"merchant": "Example Mart", "date": "2026-11-18", "total": "125.00"}
    }]
    suggestions = suggest_matches(
        [{"description": "EXAMPLE MART POS", "date": "2026-11-19", "amount": "125.00"}],
        receipts,
    )
    candidate = suggestions[0]["candidates"][0]
    assert candidate["receipt_id"] == "r-1"
    assert candidate["confidence"] >= 75
    assert "Exact amount match" in candidate["reasons"]
    assert suggestions[0]["requires_human_confirmation"] is True
