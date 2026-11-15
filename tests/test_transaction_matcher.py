from backend.app.transaction_matcher import match_transaction_to_receipts


def test_matcher_requires_same_currency_and_amount():
    transaction = {
        "amount": "-1250.00", "currency_code": "INR",
        "transaction_date": "2026-11-15", "description": "Acme Store",
    }
    receipts = [
        {"receipt_id": "r1", "total_amount": "1250.00", "currency_code": "INR",
         "document_date": "2026-11-15", "merchant_name": "Acme Store"},
        {"receipt_id": "r2", "total_amount": "1250.00", "currency_code": "USD",
         "document_date": "2026-11-15", "merchant_name": "Acme Store"},
        {"receipt_id": "r3", "total_amount": "1300.00", "currency_code": "INR",
         "document_date": "2026-11-15", "merchant_name": "Acme Store"},
    ]
    matches = match_transaction_to_receipts(transaction, receipts)
    assert len(matches) == 1
    assert matches[0]["receipt_id"] == "r1"
    assert matches[0]["requires_confirmation"] is True


def test_matcher_rejects_date_outside_tolerance():
    transaction = {
        "amount": "100", "currency_code": "INR",
        "transaction_date": "2026-11-20", "description": "Store",
    }
    receipt = {"receipt_id": "r1", "total_amount": "100", "currency_code": "INR",
               "document_date": "2026-11-01", "merchant_name": "Store"}
    assert match_transaction_to_receipts(transaction, [receipt]) == []
