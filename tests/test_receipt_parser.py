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


HOTEL_OCR_SAMPLE = """
@ 1230 Roed, Besgaiury » $40001, Karnataka, india HOTEL BILL
BRB & +91809234 S678 Invoice No: HB2026101501
SUNRISE HOTEL © nfopeuncisehotetin Date: 16 Oct 2026
GuestNeme : Rahul Meta Room No. : w2
1 Rocen Charges (Deka Roce) 99631 Sights B.- 3,000.00 9,000.00
2 Breakfast (2 Goests) 996331 3 Nights 500.09 1500.00
4 Room Service (Food & Beverages) 196331 600.00 660.00
CGST @ 6% 684.00
Round Off 18.00
Amount Paid + €1Z 990.00 Total Amount 12,750.00
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
    assert extract_final_payment("Final payment - UP! 5,192.50") == "5,192.50"


def test_missing_financial_field_requires_review():
    receipt = parse_receipt("Subtotal 100.00\nTotal 100.00")
    result = validate_parsed_receipt(receipt)
    assert result["overall_status"] == "review_required"
    assert "cgst" in result["missing_fields"]


def test_hotel_invoice_alternate_labels_are_extracted():
    receipt = parse_receipt(HOTEL_OCR_SAMPLE)
    assert receipt["bill_number"] == "HB2026101501"
    assert receipt["issue_date"] == "16 Oct 2026"
    assert receipt["guest_name"] == "Rahul Meta"
    assert receipt["cgst"] == "684.00"
    assert receipt["round_off"] == "18.00"
    assert receipt["total"] == "12750.00"
    assert receipt["final_payment"] == "990.00"


def test_missing_tax_or_advance_is_not_guessed_for_hotel_invoice():
    receipt = parse_receipt(HOTEL_OCR_SAMPLE)
    result = validate_parsed_receipt(receipt)
    assert result["overall_status"] == "review_required"
    assert "subtotal" in result["missing_fields"]
    assert "sgst" in result["missing_fields"]
    assert "advance" in result["missing_fields"]
