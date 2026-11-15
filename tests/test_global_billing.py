from backend.app.global_billing import detect_country, detect_currency, parse_global_document, validate_global_document

def test_indian_gst_receipt_uses_dynamic_tax_entries():
    text = "ABC STORE\nGSTIN 19ABCDE1234F1Z5\nSubtotal ₹1,000.00\nCGST 9% ₹90.00\nSGST 9% ₹90.00\nGrand Total ₹1,180.00"
    parsed = parse_global_document(text)
    assert parsed["country"]["country_code"] == "IN"
    assert parsed["currency"]["currency_code"] == "INR"
    assert {t["name"] for t in parsed["taxes"]} == {"CGST", "SGST"}
    assert parsed["amounts"]["tax_total"] == "180.00"
    assert validate_global_document(parsed)["checks"][0]["status"] == "passed"

def test_us_occupancy_tax_is_not_called_gst():
    text = "Grandview Heights Hotel\nAspen, CO 81611 USA\nInvoice OV-88201\nSubtotal $2,280.00\nOccupancy Tax $257.64\nTOTAL DUE $2,537.64"
    parsed = parse_global_document(text)
    assert parsed["country"]["country_code"] == "US"
    assert parsed["currency"]["currency_code"] == "USD"
    assert parsed["taxes"][0]["category"] == "local_hospitality_tax"
    assert validate_global_document(parsed)["checks"][0]["status"] == "passed"

def test_yen_symbol_without_context_is_ambiguous():
    assert detect_currency("Total ¥500", None)["currency_code"] is None

def test_japanese_invoice_clues():
    assert detect_country("適格請求書 消費税 10% 合計 1100円")["country_code"] == "JP"

def test_missing_tax_is_not_a_required_field():
    parsed = parse_global_document("Corner Shop\nTotal INR 500.00")
    assert parsed["taxes"] == []
    assert parsed["amounts"]["grand_total"]["value"] == "500.00"

def test_indian_country_context_resolves_ocr_noisy_foreign_symbols_to_inr():
    result = detect_currency("HOTEL BILL Karnataka, India CGST 6% 684.00 Amount Paid €1Z 990.00", "IN")
    assert result["currency_code"] == "INR"
    assert result["confidence"] == "medium"

def test_bare_dollar_without_country_is_ambiguous():
    result = detect_currency("Total $250.00", None)
    assert result["currency_code"] is None
    assert result["confidence"] == "ambiguous"

def test_explicit_currency_code_wins():
    result = detect_currency("Invoice total USD 250.00", None)
    assert result["currency_code"] == "USD"
    assert result["confidence"] == "high"
