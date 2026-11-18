"""Explainable, non-automatic receipt-to-statement matching suggestions."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
import unicodedata


def _money(value) -> Decimal | None:
    if value is None:
        return None
    raw = str(value).strip()
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("()").replace(",", "")
    raw = re.sub(r"(?i)\b(?:INR|USD|EUR|GBP|RS\.?|RUPEES?)\b", "", raw)
    raw = re.sub(r"[^0-9.\-+]", "", raw)
    try:
        result = Decimal(raw)
        return -abs(result) if negative else result
    except (InvalidOperation, ValueError):
        return None


def _date(value) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _tokens(value) -> set[str]:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return {token for token in re.findall(r"[a-z0-9]{3,}", text)
            if token not in {"private", "limited", "ltd", "store", "shop", "the"}}


def _score(line: dict, candidate: dict) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    line_amount = _money(line.get("amount"))
    receipt_amount = _money(candidate.get("receipt", {}).get("total"))
    if line_amount is not None and receipt_amount is not None:
        difference = abs(line_amount - receipt_amount)
        if difference == 0:
            score += 0.55
            reasons.append("Exact amount match")
        elif difference <= Decimal("0.01"):
            score += 0.50
            reasons.append("Amount matches within one paisa/cent")
        elif max(abs(line_amount), abs(receipt_amount), Decimal("1")) * Decimal("0.02") >= difference:
            score += 0.30
            reasons.append("Amount is within 2%")
    line_date = _date(line.get("date"))
    receipt_date = _date(candidate.get("receipt", {}).get("date"))
    if line_date and receipt_date:
        days = abs((line_date - receipt_date).days)
        if days == 0:
            score += 0.25
            reasons.append("Same transaction date")
        elif days <= 2:
            score += 0.20
            reasons.append("Dates are within 2 days")
        elif days <= 5:
            score += 0.12
            reasons.append("Dates are within 5 days")
    statement_tokens = _tokens(line.get("description"))
    merchant_tokens = _tokens(candidate.get("receipt", {}).get("merchant"))
    if statement_tokens and merchant_tokens:
        overlap = len(statement_tokens & merchant_tokens) / max(1, min(len(statement_tokens), len(merchant_tokens)))
        if overlap:
            score += 0.20 * overlap
            reasons.append("Merchant text overlaps")
    return min(score, 1.0), reasons


def suggest_matches(statement_lines: list[dict], receipts: list[dict]) -> list[dict]:
    """Return ranked candidates; suggestions never create or approve a match."""
    output = []
    for index, line in enumerate(statement_lines):
        ranked = []
        for receipt in receipts:
            if receipt.get("status") == "rejected":
                continue
            score, reasons = _score(line, receipt)
            if score >= 0.35:
                ranked.append({
                    "receipt_id": receipt["receipt_id"],
                    "status": receipt.get("status"),
                    "merchant": receipt.get("receipt", {}).get("merchant"),
                    "receipt_date": receipt.get("receipt", {}).get("date"),
                    "receipt_total": receipt.get("receipt", {}).get("total"),
                    "confidence": round(score * 100),
                    "reasons": reasons,
                })
        ranked.sort(key=lambda item: (-item["confidence"], item["receipt_id"]))
        output.append({
            "statement_line": index,
            "description": str(line.get("description") or "")[:200],
            "amount": str(line.get("amount") or "")[:40],
            "date": str(line.get("date") or "")[:40],
            "candidates": ranked[:3],
            "requires_human_confirmation": True,
        })
    return output
