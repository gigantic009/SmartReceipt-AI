import pytest

from backend.app.coordinate_extractor import (
    extract_field,
    find_amount_candidates,
    find_label,
    normalize_amount_token,
)


def word(text, left, top=10, width=20, height=8, confidence=90):
    return {
        "text": text,
        "left": left,
        "top": top,
        "width": width,
        "height": height,
        "confidence": confidence,
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("@12,390.00", "12,390.00"),
        ("“18.00", "18.00"),
        ("11,400.00", "11,400.00"),
        ("6%", None),
        ("12.390.00", None),
        ("abc", None),
        ("12,39,000.00", None),
    ],
)
def test_normalize_amount_token_is_conservative(raw, expected):
    assert normalize_amount_token(raw) == expected


def test_find_label_matches_words_by_position_not_list_order():
    words = [
        word("Payment", 10, 10),
        word("Round", 300, 50),
        word("OtherColumn", 120, 50),
        word("Off", 325, 50),
    ]

    result = find_label(words, ("round", "off"))

    assert result is not None
    assert [item["text"] for item in result] == ["Round", "Off"]


def test_amount_candidates_exclude_percentage_and_keep_amount():
    words = [
        word("CGST", 300, 50, width=30),
        word("@", 335, 50, width=5),
        word("6%", 345, 50, width=15),
        word("684.00", 430, 50, width=40, confidence=93),
    ]

    label = find_label(words, ("cgst",))
    candidates = find_amount_candidates(words, label)

    assert [item["normalized"] for item in candidates] == ["684.00"]


def test_split_amount_tokens_are_not_joined_or_guessed():
    words = [
        word("SGST", 300, 80, width=30, confidence=86),
        word("@", 335, 80, width=5),
        word("6%", 345, 80, width=15),
        word("684", 430, 80, width=25, confidence=62),
        word("00", 456, 80, width=15, confidence=62),
    ]

    result = extract_field(words, "sgst")

    assert result["value"] is None
    assert result["status"] == "multiple_amount_tokens_review"
    assert [item["raw"] for item in result["candidates"]] == ["684", "00"]


def test_low_confidence_amount_is_proposed_but_not_finalized():
    words = [
        word("Total", 300, 100, width=25, confidence=95),
        word("Amount", 328, 100, width=30, confidence=95),
        word("12,750.00", 430, 100, width=45, confidence=57),
    ]

    result = extract_field(words, "total")

    assert result["value"] is None
    assert result["proposed_value"] == "12,750.00"
    assert result["status"] == "needs_review"


def test_missing_label_is_reported():
    result = extract_field([word("Subtotal", 10)], "sgst")
    assert result["status"] == "label_not_found"
    assert result["value"] is None
