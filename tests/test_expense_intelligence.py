from backend.app.expense_intelligence import suggest_category


def test_hotel_receipt_is_suggested_as_travel():
    result = suggest_category("Sunrise Hotel", "Room charges and breakfast")
    assert result["category"] == "Travel"
    assert result["method"] == "keyword_suggestion"


def test_unknown_document_remains_uncategorized():
    result = suggest_category("Unknown Vendor", "Document total 100")
    assert result["category"] == "Uncategorized"
    assert result["confidence"] == "unknown"
