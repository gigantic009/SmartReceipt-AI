from backend.app.date_normalizer import normalize_document_date


def test_iso_date_is_preserved():
    result = normalize_document_date("2026-11-16", "IN")
    assert result["value"] == "2026-11-16"
    assert result["confidence"] == "high"


def test_us_numeric_date_uses_month_day_order():
    result = normalize_document_date("04/05/2026", "US")
    assert result["value"] == "2026-04-05"


def test_numeric_date_without_locale_remains_ambiguous():
    result = normalize_document_date("04/05/2026", None)
    assert result["value"] is None
    assert result["ambiguous"] is True


def test_day_over_twelve_disambiguates_date():
    result = normalize_document_date("17/04/2026", None)
    assert result["value"] == "2026-04-17"
