from backend.app.receipt_parser import (
    extract_amount,
    extract_final_payment,
    parse_receipt,
    validate_parsed_receipt,
)


SAMPLE_RECEIPT = """
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


def test_parse_receipt_extracts_and_normalizes_fields():
    receipt = parse_receipt(SAMPLE_RECEIPT)

    assert receipt["bill_number"] == "DEMO-H-001"
    assert receipt["issue_date"] == "18 Sep 2026"
    assert receipt["guest_name"] == "Aarav Menta"
    assert receipt["subtotal"] == "6850.00"
    assert receipt["cgst"] == "171.25"
    assert receipt["total"] == "7192.50"
    assert receipt["final_payment"] == "5192.50"
    assert receipt["balance"] == "0.00"


def test_parser_preserves_raw_amounts():
    receipt = parse_receipt(SAMPLE_RECEIPT)

    assert receipt["raw_amounts"]["cgst"] == "171,25"
    assert receipt["cgst"] == "171.25"


def test_total_label_does_not_match_subtotal():
    text = "Subtotal 6,850.00\nTotal 7,192.50"

    assert extract_amount(text, "Total") == "7,192.50"


def test_extract_final_payment_with_payment_method():
    assert extract_final_payment(
        "Final payment - UP! 5,192.50"
    ) == "5,192.50"


def test_missing_financial_field_requires_review():
    receipt = parse_receipt("Subtotal 100.00\nTotal 100.00")
    result = validate_parsed_receipt(receipt)

    assert result["overall_status"] == "review_required"
    assert "cgst" in result["missing_fields"]
