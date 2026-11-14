from backend.app.ocr_corrector import check_confidence, correct_word, normalize_amount


def test_common_ocr_word_correction():
    result = correct_word("UP!")

    assert result["corrected"] == "UPI"
    assert result["was_corrected"] is True


def test_confidence_threshold_requires_review():
    assert check_confidence(95)["review_required"] is False
    assert check_confidence(72)["review_required"] is True
    assert check_confidence(40)["status"] == "low"


def test_indian_decimal_comma_normalization():
    result = normalize_amount("850,00")

    assert result["valid"] is True
    assert result["normalized"] == "850.00"


def test_thousands_separator_normalization():
    result = normalize_amount("6,850.00")

    assert result["valid"] is True
    assert result["normalized"] == "6850.00"


def test_invalid_amount_is_not_guessed():
    result = normalize_amount("not-an-amount")

    assert result["valid"] is False
    assert result["normalized"] is None
