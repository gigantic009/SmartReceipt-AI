"""Grounded finance question answering over the local SQLite ledger."""
from __future__ import annotations
import re
from backend.app.database import get_analytics, get_budget_status, list_receipts

CURRENCY_CODES = {"INR", "USD", "EUR", "GBP", "JPY", "CNY", "AUD", "CAD", "CHF", "SGD", "AED"}
CATEGORIES = ("Travel", "Food & Dining", "Groceries", "Shopping", "Utilities",
              "Healthcare", "Office & Software", "Uncategorized")


def answer_financial_question(question: str) -> dict:
    """Answer supported ledger questions with explicit database evidence."""
    q = (question or "").strip()
    if not q:
        return {"answer": "Ask about spending, categories, budgets or documents needing review.", "evidence": [], "intent": "help"}
    analytics = get_analytics()
    currency = next((code for code in CURRENCY_CODES if re.search(r"\b" + code + r"\b", q, re.I)), None)
    category = next((name for name in CATEGORIES if name.casefold() in q.casefold()), None)

    if re.search(r"\b(review|uncertain|pending)\b|needs attention", q, re.I):
        records = list_receipts(status="review_required", limit=50)
        return {
            "answer": f"{len(records)} saved document(s) currently need review.",
            "intent": "review_queue",
            "evidence": [{"receipt_id": item["receipt_id"], "merchant": item.get("merchant_name"),
                          "date": item.get("document_date"), "status": item.get("status")}
                         for item in records],
        }

    if "budget" in q.casefold() or "limit" in q.casefold():
        budgets = get_budget_status()
        if currency:
            budgets = [item for item in budgets if item["currency_code"] == currency]
        if category:
            budgets = [item for item in budgets if item.get("category") in {None, category}]
        return {
            "answer": f"Found {len(budgets)} matching budget(s). Spending and remaining amounts are shown in each budget's own currency.",
            "intent": "budget_status",
            "evidence": budgets,
        }

    if category:
        amounts = analytics["spend_by_category"].get(category, {})
        if currency:
            value = amounts.get(currency)
            answer = f"Recorded spend for {category} in {currency}: {value:.2f}." if value is not None else f"No recorded {category} spend in {currency}."
        else:
            answer = f"Recorded {category} spend by currency: " + (
                ", ".join(f"{code} {amount:.2f}" for code, amount in sorted(amounts.items())) or "no records"
            ) + "."
        return {"answer": answer, "intent": "category_spend", "evidence": [{"category": category, "amounts_by_currency": amounts}]}

    if currency and any(word in q.casefold() for word in ("spend", "spent", "total", "expense", "amount")):
        value = analytics["spend_by_currency"].get(currency, 0.0)
        return {"answer": f"Recorded total spend in {currency}: {value:.2f}.", "intent": "currency_spend",
                "evidence": [{"currency": currency, "amount": value}]}

    if any(word in q.casefold() for word in ("how many", "count", "documents", "receipts", "invoices")):
        return {"answer": f"The ledger contains {analytics['document_count']} document(s) and {analytics['expense_count']} manual expense(s).",
                "intent": "ledger_counts", "evidence": [{"document_count": analytics["document_count"],
                "expense_count": analytics["expense_count"]}]}

    return {
        "answer": "I can answer questions about total spend by currency, spending by category, budget utilization, document counts and documents needing review. Include a currency code such as INR or USD when asking about money.",
        "intent": "help",
        "evidence": [],
    }
