import pytest

from backend.app.coordinate_extractor import (
    extract_field,
    find_amount_candidates,
    find_label,
    interpret_round_off_crop_tokens,
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



def test_amount_paid_excludes_nearby_payment_date_row():
    words = [
        word("Amount", 20, 261, width=28, height=8, confidence=93),
        word("Paid", 50, 261, width=20, height=8, confidence=74),
        word("@12,390.00", 86, 263, width=55, height=8, confidence=28),
        word("1S", 86, 253, width=10, height=8, confidence=15),
        word("Oct", 96, 253, width=12, height=8, confidence=15),
        word("2026", 108, 253, width=25, height=8, confidence=40),
    ]

    result = extract_field(words, "amount_paid")

    assert result["status"] == "needs_review"
    assert result["proposed_value"] == "12,390.00"
    assert result["value"] is None


def test_sgst_crop_accepts_single_high_confidence_token():
    from backend.app.coordinate_extractor import interpret_sgst_crop_tokens

    result = interpret_sgst_crop_tokens(
        [{"text": "684.00", "confidence": 92}],
        label_confidence=86,
    )

    assert result["status"] == "recognized"
    assert result["value"] == "684.00"
    assert result["confidence"] == 92


def test_sgst_crop_keeps_low_confidence_token_for_review():
    from backend.app.coordinate_extractor import interpret_sgst_crop_tokens

    result = interpret_sgst_crop_tokens(
        [{"text": "684.00", "confidence": 74}],
        label_confidence=86,
    )

    assert result["status"] == "needs_review"
    assert result["value"] is None
    assert result["proposed_value"] == "684.00"


def test_sgst_crop_does_not_join_multiple_tokens():
    from backend.app.coordinate_extractor import interpret_sgst_crop_tokens

    result = interpret_sgst_crop_tokens(
        [
            {"text": "684", "confidence": 92},
            {"text": "00", "confidence": 92},
        ],
        label_confidence=86,
    )

    assert result["status"] == "multiple_amount_tokens_review"
    assert result["value"] is None
    assert len(result["candidates"]) == 2



def test_total_amount_crop_accepts_single_high_confidence_token():
    from backend.app.coordinate_extractor import interpret_total_amount_crop_tokens

    result = interpret_total_amount_crop_tokens(
        [{"text": "12,750.00", "confidence": 96}],
        label_confidence=95,
    )

    assert result["status"] == "recognized"
    assert result["value"] == "12,750.00"
    assert result["confidence"] == 96


def test_total_amount_crop_keeps_low_confidence_token_for_review():
    from backend.app.coordinate_extractor import interpret_total_amount_crop_tokens

    result = interpret_total_amount_crop_tokens(
        [{"text": "12,750.00", "confidence": 84}],
        label_confidence=95,
    )

    assert result["status"] == "needs_review"
    assert result["value"] is None
    assert result["proposed_value"] == "12,750.00"


def test_total_amount_crop_does_not_join_multiple_tokens():
    from backend.app.coordinate_extractor import interpret_total_amount_crop_tokens

    result = interpret_total_amount_crop_tokens(
        [
            {"text": "12,750", "confidence": 96},
            {"text": "00", "confidence": 96},
        ],
        label_confidence=95,
    )

    assert result["status"] == "multiple_amount_tokens_review"
    assert result["value"] is None
    assert len(result["candidates"]) == 2


def test_total_amount_crop_reports_missing_token():
    from backend.app.coordinate_extractor import interpret_total_amount_crop_tokens

    result = interpret_total_amount_crop_tokens([], label_confidence=95)

    assert result["status"] == "amount_not_found"
    assert result["value"] is None



def test_round_off_crop_accepts_single_high_confidence_signed_token():
    result = interpret_round_off_crop_tokens(
        [{"text": "-18.00", "confidence": 92}],
        label_confidence=95,
    )

    assert result["status"] == "recognized"
    assert result["value"] == "-18.00"
    assert result["confidence"] == 92


def test_round_off_crop_keeps_low_confidence_token_for_review():
    result = interpret_round_off_crop_tokens(
        [{"text": "-18.00", "confidence": 84}],
        label_confidence=95,
    )

    assert result["status"] == "needs_review"
    assert result["value"] is None
    assert result["proposed_value"] == "-18.00"


def test_round_off_crop_does_not_join_multiple_tokens():
    result = interpret_round_off_crop_tokens(
        [
            {"text": "-18", "confidence": 92},
            {"text": "00", "confidence": 92},
        ],
        label_confidence=95,
    )

    assert result["status"] == "multiple_amount_tokens_review"
    assert result["value"] is None
    assert len(result["candidates"]) == 2


def test_round_off_crop_reports_missing_token():
    result = interpret_round_off_crop_tokens([], label_confidence=95)

    assert result["status"] == "amount_not_found"
    assert result["value"] is None



def test_round_off_crop_extractor_keeps_low_confidence_for_review(monkeypatch):
    import numpy as np
    from backend.app import coordinate_extractor as extractor

    monkeypatch.setattr(
        extractor.pytesseract,
        "image_to_data",
        lambda *args, **kwargs: {
            "text": ["-18.00"],
            "conf": ["84"],
        },
    )
    image = np.zeros((333, 500, 3), dtype=np.uint8)
    label = [word("Round", 300), word("Off", 325)]

    result = extractor.extract_round_off_crop_field(image, label)

    assert result["status"] == "needs_review"
    assert result["value"] is None
    assert result["proposed_value"] == "-18.00"
    assert result["ocr_method"] == "grayscale 4x PSM 7"
    assert result["crop"] == extractor.ROUND_OFF_AMOUNT_CROP


def test_round_off_crop_extractor_accepts_high_confidence_signed_token(monkeypatch):
    import numpy as np
    from backend.app import coordinate_extractor as extractor

    monkeypatch.setattr(
        extractor.pytesseract,
        "image_to_data",
        lambda *args, **kwargs: {
            "text": ["-18.00"],
            "conf": ["92"],
        },
    )
    image = np.zeros((333, 500, 3), dtype=np.uint8)
    label = [word("Round", 300), word("Off", 325)]

    result = extractor.extract_round_off_crop_field(image, label)

    assert result["status"] == "recognized"
    assert result["value"] == "-18.00"


def test_round_off_crop_extractor_reports_missing_label():
    import numpy as np
    from backend.app.coordinate_extractor import extract_round_off_crop_field

    image = np.zeros((333, 500, 3), dtype=np.uint8)
    result = extract_round_off_crop_field(image, [])

    assert result["status"] == "label_not_found"
    assert result["value"] is None
