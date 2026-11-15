"""Conservative line-item extraction from OCR text.

Only rows with a plausible description and trailing monetary amount are emitted.
This baseline deliberately avoids inventing quantities, unit prices or tax rates.
"""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation

SUMMARY_LABELS = re.compile(
    r"\b(sub\s*total|subtotal|grand\s*total|total\s*due|invoice\s*total|"
    r"total\s*amount|tax|vat|gst|cgst|sgst|igst|discount|balance|amount\s*paid|"
    r"change|cash|card|visa|mastercard|payment|round\s*off|service\s*charge)\b",
    re.I,
)
AMOUNT_AT_END = re.compile(
    r"(?P<amount>[-+]?\s*(?:₹|\$|€|£|INR|USD|EUR|GBP)?\s*\(?\d[\d,]*(?:\.\d{1,4})?\)?\s*)$",
    re.I,
)
QTY_PREFIX = re.compile(r"^\s*(?P<quantity>\d+(?:\.\d+)?)\s*[xX×]\s*(?P<description>.+)$")


def extract_line_items(text: str) -> list[dict]:
    items = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip(" |\t")
        if len(line) < 5 or SUMMARY_LABELS.search(line):
            continue
        match = AMOUNT_AT_END.search(line)
        if not match:
            continue
        description = line[:match.start()].strip(" :-|")
        if len(description) < 2 or not re.search(r"[A-Za-z\u0080-\uffff]", description):
            continue
        token = match.group("amount").strip().replace(",", "").replace(" ", "")
        token = token.replace("₹", "").replace("$", "").replace("€", "").replace("£", "")
        token = re.sub(r"^(INR|USD|EUR|GBP)", "", token, flags=re.I)
        token = token.strip("()")
        try:
            amount = Decimal(token)
        except InvalidOperation:
            continue
        if amount < 0:
            continue
        quantity = None
        quantity_match = QTY_PREFIX.match(description)
        if quantity_match:
            quantity = quantity_match.group("quantity")
            description = quantity_match.group("description").strip()
        items.append({
            "description": description,
            "quantity": quantity,
            "unit_price": None,
            "line_total": format(amount, "f"),
            "raw_text": line,
            "confidence": "candidate",
            "needs_review": True,
        })
    return items
