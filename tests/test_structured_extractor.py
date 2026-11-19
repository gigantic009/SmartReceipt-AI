from backend.app.structured_extractor import extract_receipt_fields


def test_rules_are_default_and_report_no_external_provider():
    receipt, metadata = extract_receipt_fields("Example Store\nTotal 25.00", mode="rules")
    assert receipt["total"] == "25.00"
    assert metadata["provider"] == "rules"
    assert metadata["requires_human_review"] is False


def test_local_model_output_is_allowlisted_and_requires_review():
    def fake_local(_ocr):
        return {
            "merchant": "Example Store",
            "total": "25.00",
            "unexpected_instruction": "ignore security",
            "raw_amounts": {"total": "fabricated"},
        }
    receipt, metadata = extract_receipt_fields(
        "Example Store\nTotal 25.00",
        mode="ollama",
        ollama_call=fake_local,
    )
    assert receipt["merchant"] == "Example Store"
    assert receipt["total"] == "25.00"
    assert "unexpected_instruction" not in receipt
    assert receipt["raw_amounts"]["total"] == "25.00"
    assert metadata["provider"] == "ollama-local"
    assert metadata["requires_human_review"] is True


def test_local_model_failure_falls_back_to_rules():
    def unavailable(_ocr):
        raise TimeoutError("model unavailable")
    receipt, metadata = extract_receipt_fields(
        "Example Store\nTotal 25.00",
        mode="ollama",
        ollama_call=unavailable,
    )
    assert receipt["total"] == "25.00"
    assert metadata["provider"] == "rules-fallback"
    assert metadata["fallback"] is True
    assert metadata["requires_human_review"] is True
