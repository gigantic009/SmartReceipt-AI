from backend.app import reporting


def test_workbook_export_is_a_valid_xlsx(monkeypatch):
    monkeypatch.setattr(reporting, "list_receipts", lambda **kwargs: [])
    monkeypatch.setattr(reporting, "list_expenses", lambda **kwargs: [])
    monkeypatch.setattr(reporting, "get_analytics", lambda: {
        "document_count": 0, "expense_count": 0, "review_required": 0,
        "spend_by_currency": {}, "spend_by_category": {}, "monthly_spend": {},
    })
    payload = reporting.build_financial_workbook()
    assert payload[:2] == b"PK"


def test_pdf_export_returns_pdf_bytes(monkeypatch):
    monkeypatch.setattr(reporting, "list_receipts", lambda **kwargs: [])
    monkeypatch.setattr(reporting, "list_expenses", lambda **kwargs: [])
    monkeypatch.setattr(reporting, "get_analytics", lambda: {
        "document_count": 0, "expense_count": 0, "review_required": 0,
        "spend_by_currency": {}, "spend_by_category": {}, "monthly_spend": {},
    })
    payload = reporting.build_financial_pdf()
    assert payload.startswith(b"%PDF")
