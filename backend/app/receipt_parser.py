import re
from decimal import Decimal

from backend.app.ocr_corrector import normalize_amount
from backend.app.validate_receipt import validate_receipt


def extract_basic_details(text: str) -> dict:
    """Extract basic receipt information from OCR text."""
    bill_match = re.search(
        r"Bill:\s*([A-Z0-9-]+)",
        text,
        re.IGNORECASE
    )
    date_match = re.search(
        r"Issued:\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})",
        text,
        re.IGNORECASE
    )
    guest_match = re.search(
        r"Guest:\s*(.+)",
        text,
        re.IGNORECASE
    )

    return {
        "bill_number": bill_match.group(1) if bill_match else None,
        "issue_date": date_match.group(1) if date_match else None,
        "guest_name": guest_match.group(1).strip() if guest_match else None
    }


def extract_amount(text: str, label: str) -> str | None:
    """Extract an amount appearing after an exact label."""
    pattern = (
        rf"(?<![A-Za-z]){re.escape(label)}"
        rf"(?![A-Za-z])\s*[:\-]?\s*"
        rf"([\d,]+(?:\.\d{{2}})?)"
    )
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1) if match else None


def extract_final_payment(text: str) -> str | None:
    """Extract the final payment amount, optionally followed by a method."""
    pattern = (
        r"Final\s+payment"
        r"(?:\s*[-:]\s*[A-Za-z!]+)?"
        r"\s*[:\-]?\s*"
        r"([\d,]+(?:\.\d{2})?)"
    )
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1) if match else None


def normalize_receipt_amount(value: str | None) -> str | None:
    """Normalize a monetary value without guessing ambiguous formats."""
    if value is None:
        return None

    result = normalize_amount(value)
    return result["normalized"] if result["valid"] else None


def parse_receipt(text: str) -> dict:
    """Extract receipt fields while retaining the original OCR amount strings."""
    raw_amounts = {
        "subtotal": extract_amount(text, "Subtotal"),
        "cgst": extract_amount(text, "CGST"),
        "sgst": extract_amount(text, "SGST"),
        "total": extract_amount(text, "Total"),
        "advance": extract_amount(text, "Advance"),
        "final_payment": extract_final_payment(text),
        "balance": extract_amount(text, "Balance")
    }

    normalized_amounts = {
        key: normalize_receipt_amount(value)
        for key, value in raw_amounts.items()
    }

    return {
        **extract_basic_details(text),
        **normalized_amounts,
        "raw_amounts": raw_amounts
    }


def validate_parsed_receipt(receipt: dict) -> dict:
    """Validate parsed financial values and identify missing required fields."""
    required_fields = (
        "subtotal",
        "cgst",
        "sgst",
        "total",
        "advance",
        "final_payment"
    )

    missing_fields = [
        field for field in required_fields
        if receipt.get(field) is None
    ]

    if missing_fields:
        return {
            "overall_status": "review_required",
            "missing_fields": missing_fields
        }

    values = {
        field: Decimal(receipt[field])
        for field in required_fields
    }
    balance = (
        Decimal(receipt["balance"])
        if receipt.get("balance") is not None
        else None
    )

    return validate_receipt(**values, balance=balance)
