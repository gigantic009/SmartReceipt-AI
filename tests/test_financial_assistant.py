from backend.app import financial_assistant


def test_financial_assistant_answers_currency_total(monkeypatch):
    monkeypatch.setattr(financial_assistant, "get_analytics", lambda: {
        "document_count": 2, "expense_count": 1, "review_required": 1,
        "spend_by_currency": {"INR": 1200.0, "USD": 10.0},
        "spend_by_category": {}, "monthly_spend": {},
    })
    result = financial_assistant.answer_financial_question("How much did I spend in INR?")
    assert result["intent"] == "currency_spend"
    assert "1200.00" in result["answer"]


def test_financial_assistant_does_not_combine_currencies_for_category(monkeypatch):
    monkeypatch.setattr(financial_assistant, "get_analytics", lambda: {
        "document_count": 0, "expense_count": 0, "review_required": 0,
        "spend_by_currency": {"INR": 100.0, "USD": 10.0},
        "spend_by_category": {"Travel": {"INR": 100.0, "USD": 10.0}},
        "monthly_spend": {},
    })
    result = financial_assistant.answer_financial_question("Show Travel spending")
    assert "INR 100.00" in result["answer"]
    assert "USD 10.00" in result["answer"]
