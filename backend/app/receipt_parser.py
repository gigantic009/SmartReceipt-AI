
import re
from backend.app.ocr_engine import extract_text
from backend.app.ocr_corrector import normalize_amount
from decimal import Decimal
from backend.app.validate_receipt import validate_receipt

def extract_basic_details(text: str) -> dict:
    """
    Extract basic receipt information from OCR text.
    """

    details = {}

    # Extract bill number
    bill_match = re.search(
        r"Bill:\s*([A-Z0-9-]+)",
        text,
        re.IGNORECASE
    )

    details["bill_number"] = (
        bill_match.group(1) if bill_match else None
    )

    # Extract issue date
    date_match = re.search(
        r"Issued:\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})",
        text,
        re.IGNORECASE
    )

    details["issue_date"] = (
        date_match.group(1) if date_match else None
    )

    # Extract guest name
    guest_match = re.search(
        r"Guest:\s*(.+)",
        text,
        re.IGNORECASE
    )

    details["guest_name"] = (
        guest_match.group(1).strip() if guest_match else None
    )

    return details


def extract_amount(text: str, label: str) -> str | None:
    """
    Extract an amount appearing after an exact label.
    """

    pattern = (
        rf"(?<![A-Za-z]){re.escape(label)}"
        rf"(?![A-Za-z])\s*[:\-]?\s*"
        rf"([\d,]+(?:\.\d{{2}})?)"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return None

def extract_final_payment(text: str) -> str | None:
    """
    Extract the final payment amount.
    """

    pattern = (
        r"Final\s+payment"
        r"(?:\s*-\s*[A-Za-z!]+)?"
        r"\s*[:\-]?\s*"
        r"([\d,]+(?:\.\d{2})?)"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return None

def normalize_receipt_amount(value: str | None) -> str | None:
    """
    Normalize an extracted receipt amount.
    Preserve None when no amount was extracted.
    """

    if value is None:
        return None

    result = normalize_amount(value)

    if result["valid"]:
        return result["normalized"]

    return None


def parse_receipt(text: str) -> dict:
    """
    Extract and normalize receipt information.
    """

    # Extract basic information
    basic_details = extract_basic_details(text)

    # Extract raw financial values
    raw_amounts = {
        "subtotal": extract_amount(text, "Subtotal"),
        "cgst": extract_amount(text, "CGST"),
        "sgst": extract_amount(text, "SGST"),
        "total": extract_amount(text, "Total"),
        "advance": extract_amount(text, "Advance"),
        "final_payment": extract_final_payment(text),
        "balance": extract_amount(text, "Balance")
    }

    # Normalize financial values
    normalized_amounts = {
        key: normalize_receipt_amount(value)
        for key, value in raw_amounts.items()
    }

    # Combine everything
    receipt = {
        **basic_details,
        **normalized_amounts
    }

    return receipt

def validate_parsed_receipt(receipt: dict) -> dict:
    """
    Validate financial values extracted from a receipt.
    """

    required_fields = [
        "subtotal",
        "cgst",
        "sgst",
        "total",
        "advance",
        "final_payment"
    ]

    # Check for missing or invalid amounts
    missing_fields = [
        field
        for field in required_fields
        if receipt.get(field) is None
    ]

    if missing_fields:
        return {
            "overall_status": "review_required",
            "missing_fields": missing_fields
        }

    # Convert normalized strings into Decimal
    result = validate_receipt(
        subtotal=Decimal(receipt["subtotal"]),
        cgst=Decimal(receipt["cgst"]),
        sgst=Decimal(receipt["sgst"]),
        advance=Decimal(receipt["advance"]),
        final_payment=Decimal(receipt["final_payment"]),
        total=Decimal(receipt["total"])
    )

    return result


if __name__ == "__main__":

    sample_text = """
    Example Garden Lodge
    Bill: DEMO-H-001 Issued: 18 Sep 2026
    Guest: Aarav Menta
    """

    result = extract_basic_details(sample_text)

    print("\n===== BASIC RECEIPT DETAILS =====\n")

    for key, value in result.items():
        print(f"{key}: {value}")

    print("\n=================================\n")
    print("\n===== FINANCIAL EXTRACTION TEST =====\n")

financial_text = """
Subtotal 6,850.00
CGST 171,25
SGST 171.25
Total 7,192.50
Advance 2,000.00
Balance 0.00
"""

for label in [
    "Subtotal",
    "CGST",
    "SGST",
    "Total",
    "Advance",
    "Balance"
]:
    print(f"{label}: {extract_amount(financial_text, label)}")

print("\n===== FINAL PAYMENT TEST =====\n")

payment_text = "Final payment - UP! 5,192.50"

print(
    "Final payment:",
    extract_final_payment(payment_text)
)

print("\n===============================\n")
print("\n===== COMPLETE RECEIPT PARSER =====\n")

full_receipt_text = """
Example Garden Lodge
Bill: DEMO-H-001 Issued: 18 Sep 2026
Guest: Aarav Menta

Subtotal 6,850.00
CGST 171,25
SGST 171.25
Total 7,192.50
Advance 2,000.00
Final payment - UP! 5,192.50
Balance 0.00
"""

parsed_receipt = parse_receipt(full_receipt_text)

for key, value in parsed_receipt.items():
    print(f"{key}: {value}")

print("\n====================================\n")
print("\n===== REAL RECEIPT OCR TEST =====\n")

receipt_path = (
    "backend/ocr_ready/"
    "12cfe97d-46fb-45fa-b618-1c18795271ba.png"
)

# Extract text from the actual receipt image
ocr_text = extract_text(receipt_path)

# Parse the extracted OCR text
actual_receipt = parse_receipt(ocr_text)

# Display extracted information
for key, value in actual_receipt.items():
    print(f"{key}: {value}")

print("\n=================================\n")
print("\n===== AMOUNT NORMALIZATION TEST =====\n")

test_amounts = [
    "171,25",
    "6,850.00",
    "7,192.50",
    "2000"
]

for amount in test_amounts:
    print(
        f"{amount} -> "
        f"{normalize_receipt_amount(amount)}"
    )

print("\n=====================================\n")
print("\n===== RECEIPT VALIDATION TEST =====\n")

# Extract text from the actual receipt
ocr_text = extract_text(receipt_path)

# Parse the receipt
parsed_receipt = parse_receipt(ocr_text)

# Validate financial information
validation_result = validate_parsed_receipt(parsed_receipt)

print("Parsed receipt:")
for key, value in parsed_receipt.items():
    print(f"{key}: {value}")

print("\nValidation result:")

for key, value in validation_result.items():
    print(f"{key}: {value}")

print("\n====================================\n")