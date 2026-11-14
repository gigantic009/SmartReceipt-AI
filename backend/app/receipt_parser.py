import re
from decimal import Decimal, InvalidOperation

from backend.app.ocr_corrector import normalize_amount
from backend.app.validate_receipt import validate_receipt


AMOUNT_TOKEN = re.compile(r"(?<![A-Za-z])(?:₹\s*)?([0-9][0-9,]*(?:\.[0-9]{1,2})?)(?![A-Za-z])")


def _lines(text: str) -> list[str]:
    """Return non-empty OCR lines while preserving useful line boundaries."""
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def _extract_labeled_value(text: str, labels: tuple[str, ...]) -> str | None:
    """Find the last plausible amount on a line containing a requested label."""
    label_pattern = re.compile(
        r"(?<![A-Za-z])(?:" + "|".join(labels) + r")(?![A-Za-z])",
        re.IGNORECASE,
    )
    for line in _lines(text):
        match = label_pattern.search(line)
        if not match:
            continue
        candidates = AMOUNT_TOKEN.findall(line[match.end():])
        if candidates:
            return candidates[-1]
    return None


def extract_basic_details(text: str) -> dict:
    """Extract common invoice identifiers, dates, and guest/customer names."""
    bill_match = re.search(
        r"\b(?:Bill(?:\s*(?:No|Number))?|Invoice\s*(?:No|Number))\s*[:#-]?\s*([A-Z0-9-]{4,})",
        text, re.IGNORECASE,
    )
    date_match = re.search(
        r"\b(?:Date|Issued|Invoice\s*Date)\s*[:#-]?\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        text, re.IGNORECASE,
    )
    guest_match = re.search(
        r"\b(?:Guest\s*(?:Name|Neme)?|Customer\s*Name|Customer)\s*[:#-]?\s*([^\r\n]+)",
        text, re.IGNORECASE,
    )
    return {
        "bill_number": bill_match.group(1).strip() if bill_match else None,
        "issue_date": date_match.group(1).strip() if date_match else None,
        "guest_name": re.split(r"\s+Room\s*(?:No|Number)\b", guest_match.group(1), maxsplit=1, flags=re.IGNORECASE)[0].strip(" :-") if guest_match else None,
    }


def extract_amount(text: str, label: str) -> str | None:
    """Extract the last amount on the line containing an exact label."""
    return _extract_labeled_value(text, (re.escape(label),))


def extract_final_payment(text: str) -> str | None:
    """Extract final payment or amount-paid values despite noisy payment labels."""
    labels = re.compile(r"(?<![A-Za-z])(?:Final\s*Payment|Amount\s*Paid|Paid\s*Amount)(?![A-Za-z])", re.IGNORECASE)
    stop_labels = re.compile(r"(?<![A-Za-z])(?:Grand\s*Total|Total\s*Amount|Invoice\s*Total|Subtotal|CGST|SGST|IGST|Round\s*Off|Balance)(?![A-Za-z])", re.IGNORECASE)
    for line in _lines(text):
        match = labels.search(line)
        if not match:
            continue
        tail = line[match.end():]
        boundary = stop_labels.search(tail)
        if boundary:
            tail = tail[:boundary.start()]
        candidates = AMOUNT_TOKEN.findall(tail)
        if candidates:
            return candidates[-1]
    return None


def normalize_receipt_amount(value: str | None) -> str | None:
    """Normalize a monetary value without guessing ambiguous formats."""
    if value is None:
        return None
    result = normalize_amount(value)
    return result["normalized"] if result["valid"] else None


def parse_receipt(text: str) -> dict:
    """Extract common receipt fields across several invoice label conventions.

    Missing values remain None. Line-item sums and missing tax components
    are never invented.
    """
    raw_amounts = {
        "subtotal": _extract_labeled_value(
            text, (r"Sub\s*Total", r"Taxable\s*Value", r"Net\s*Amount")
        ),
        "cgst": _extract_labeled_value(text, (r"CGST",)),
        "sgst": _extract_labeled_value(text, (r"SGST",)),
        "igst": _extract_labeled_value(text, (r"IGST",)),
        "total": _extract_labeled_value(
            text, (r"Grand\s*Total", r"Total\s*Amount", r"Invoice\s*Total", r"Total")
        ),
        "advance": _extract_labeled_value(
            text, (r"Advance", r"Deposit", r"Amount\s*Received\s*Earlier")
        ),
        "final_payment": extract_final_payment(text),
        "balance": _extract_labeled_value(
            text, (r"Balance\s*Due", r"Outstanding", r"Due\s*Amount", r"Balance")
        ),
        "round_off": _extract_labeled_value(text, (r"Round\s*Off",)),
    }
    normalized_amounts = {
        key: normalize_receipt_amount(value)
        for key, value in raw_amounts.items()
    }
    raw_amounts["amount_paid"] = raw_amounts["final_payment"]
    normalized_amounts["amount_paid"] = normalized_amounts["final_payment"]
    return {
        **extract_basic_details(text),
        **normalized_amounts,
        "raw_amounts": raw_amounts,
    }


def validate_parsed_receipt(receipt: dict) -> dict:
    """Validate financial fields and list required values that were not found."""
    required_fields = (
        "subtotal", "cgst", "sgst", "total", "advance", "final_payment"
    )
    missing_fields = [
        field for field in required_fields if receipt.get(field) is None
    ]
    if missing_fields:
        return {
            "overall_status": "review_required",
            "missing_fields": missing_fields,
        }
    try:
        values = {field: Decimal(receipt[field]) for field in required_fields}
        balance = (
            Decimal(receipt["balance"])
            if receipt.get("balance") is not None else None
        )
        return validate_receipt(**values, balance=balance)
    except (InvalidOperation, TypeError, ValueError):
        return {
            "overall_status": "review_required",
            "missing_fields": [],
            "reason": "One or more extracted monetary values could not be validated.",
        }
