"""Explainable receipt-to-bank-transaction candidate matching."""
from __future__ import annotations
from datetime import date
from difflib import SequenceMatcher
from decimal import Decimal, InvalidOperation


def _date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def match_transaction_to_receipts(transaction: dict, receipts: list[dict]) -> list[dict]:
    candidates = []
    try:
        tx_amount = abs(Decimal(str(transaction["amount"])))
    except (InvalidOperation, KeyError, TypeError):
        return []
    tx_currency = transaction.get("currency_code")
    tx_date = _date(transaction.get("transaction_date"))
    tx_merchant = (transaction.get("merchant_name") or transaction.get("description") or "").casefold()

    for receipt in receipts:
        if receipt.get("currency_code") != tx_currency:
            continue
        try:
            receipt_amount = abs(Decimal(str(receipt.get("total_amount"))))
        except (InvalidOperation, TypeError):
            continue
        difference = abs(tx_amount - receipt_amount)
        if difference > Decimal("0.01"):
            continue
        receipt_date = _date(receipt.get("document_date"))
        day_gap = abs((tx_date - receipt_date).days) if tx_date and receipt_date else None
        if day_gap is not None and day_gap > 7:
            continue
        merchant = (receipt.get("merchant_name") or "").casefold()
        merchant_score = SequenceMatcher(None, tx_merchant, merchant).ratio() if merchant else 0.0
        date_score = 1.0 - (day_gap / 7) if day_gap is not None else 0.5
        amount_score = 1.0 if difference == 0 else 0.95
        score = round(amount_score * 0.65 + date_score * 0.2 + merchant_score * 0.15, 3)
        candidates.append({
            "receipt_id": receipt["receipt_id"],
            "merchant_name": receipt.get("merchant_name"),
            "total_amount": receipt.get("total_amount"),
            "currency_code": receipt.get("currency_code"),
            "document_date": receipt.get("document_date"),
            "amount_difference": format(difference, "f"),
            "date_difference_days": day_gap,
            "merchant_similarity": round(merchant_score, 3),
            "score": score,
            "requires_confirmation": True,
        })
    return sorted(candidates, key=lambda item: item["score"], reverse=True)
