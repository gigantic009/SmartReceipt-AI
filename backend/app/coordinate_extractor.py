"""Experimental coordinate-aware OCR for receipt layouts.

This utility is intentionally separate from the production upload pipeline.
It preserves OCR evidence and refuses to invent values when tokens are split
or ambiguous.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import cv2
import pytesseract
from pytesseract import Output


TESSERACT_DEFAULT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
DEFAULT_SCALE = 3
DEFAULT_VERTICAL_TOLERANCE = 6
SGST_AMOUNT_CROP = (445, 235, 485, 250)
SGST_CROP_SCALE = 5
SGST_CROP_CONFIDENCE_THRESHOLD = 85
TOTAL_AMOUNT_CROP = (441, 265, 490, 280)
TOTAL_AMOUNT_CROP_SCALE = 3
TOTAL_AMOUNT_CROP_CONFIDENCE_THRESHOLD = 85

# Coordinates are in the original 500x333 sample receipt image.
# Adjust these regions for a different receipt template.
DEFAULT_REGIONS = {
    "tax_and_total": (15, 212, 490, 285),
    "payment_details": (15, 214, 275, 295),
}

FIELD_LABELS = {
    "subtotal": ("subtotal",),
    "cgst": ("cgst",),
    "sgst": ("sgst",),
    "round_off": ("round", "off"),
    "total": ("total", "amount"),
    "amount_paid": ("amount", "paid"),
}

# PSM 6 reads the sample's complete tax block better. PSM 11 detects
# the isolated SGST label, although its amount is split in the sample.
FIELD_PSM = {
    "subtotal": 6,
    "cgst": 6,
    "sgst": 11,
    "round_off": 6,
    "total": 6,
    "amount_paid": 6,
}


def configure_tesseract(executable: Path = TESSERACT_DEFAULT) -> None:
    """Use the common Windows install when present; otherwise use PATH."""
    if executable.is_file():
        pytesseract.pytesseract.tesseract_cmd = str(executable)


def normalize_label_token(value: str) -> str:
    """Normalize label words without changing their meaning."""
    return re.sub(r"[^a-z]", "", value.casefold())


def normalize_amount_token(value: str) -> str | None:
    """Strip surrounding OCR punctuation, but reject malformed numbers."""
    token = value.strip()

    # A percentage is a rate, not a monetary amount.
    if "%" in token:
        return None

    token = re.sub(r"^[^0-9]+", "", token)
    token = re.sub(r"[^0-9.,]+$", "", token)

    if not re.fullmatch(r"\d[\d,]*(?:\.\d{1,2})?", token):
        return None

    integer_part = token.split(".", 1)[0]
    if "," in integer_part and not re.fullmatch(r"\d{1,3}(?:,\d{3})+", integer_part):
        return None

    return token


def prepare_region(
    image: Any,
    coordinates: tuple[int, int, int, int],
    scale: int = DEFAULT_SCALE,
):
    left, top, right, bottom = coordinates
    crop = image[top:bottom, left:right]

    if crop.size == 0:
        raise ValueError(f"Invalid or empty image region: {coordinates}")

    enlarged = cv2.resize(
        crop,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_CUBIC,
    )
    return cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)


def extract_words(
    image: Any,
    coordinates: tuple[int, int, int, int],
    psm: int,
    scale: int = DEFAULT_SCALE,
) -> list[dict[str, Any]]:
    """Return OCR words with confidence and coordinates in source-image pixels."""
    gray = prepare_region(image, coordinates, scale)
    data = pytesseract.image_to_data(
        gray,
        lang="eng",
        config=f"--oem 3 --psm {psm}",
        output_type=Output.DICT,
    )

    left_offset, top_offset, _, _ = coordinates
    words: list[dict[str, Any]] = []

    for index, raw_text in enumerate(data["text"]):
        text = raw_text.strip()
        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            continue

        if not text or confidence < 0:
            continue

        words.append(
            {
                "text": text,
                "confidence": confidence,
                "left": left_offset + data["left"][index] / scale,
                "top": top_offset + data["top"][index] / scale,
                "width": data["width"][index] / scale,
                "height": data["height"][index] / scale,
                "psm": psm,
            }
        )

    return words


def read_region_text(
    image: Any,
    coordinates: tuple[int, int, int, int],
    psm: int,
    scale: int = DEFAULT_SCALE,
) -> str:
    gray = prepare_region(image, coordinates, scale)
    return pytesseract.image_to_string(
        gray,
        lang="eng",
        config=f"--oem 3 --psm {psm}",
    ).strip()


def find_label(
    words: list[dict[str, Any]],
    label_parts: tuple[str, ...],
    vertical_tolerance: float = DEFAULT_VERTICAL_TOLERANCE,
) -> list[dict[str, Any]] | None:
    """Find multiword labels by spatial proximity, not OCR list order."""
    normalized_parts = tuple(normalize_label_token(part) for part in label_parts)

    for first in words:
        if normalize_label_token(first["text"]) != normalized_parts[0]:
            continue

        matched = [first]
        previous = first

        for expected in normalized_parts[1:]:
            previous_right = previous["left"] + previous["width"]
            options = [
                candidate
                for candidate in words
                if candidate is not previous
                and normalize_label_token(candidate["text"]) == expected
                and candidate["left"] > previous_right
                and candidate["left"] - previous_right <= 45
                and abs(
                    (candidate["top"] + candidate["height"] / 2)
                    - (previous["top"] + previous["height"] / 2)
                ) <= vertical_tolerance
            ]

            if not options:
                break

            next_word = min(options, key=lambda item: item["left"])
            matched.append(next_word)
            previous = next_word

        if len(matched) == len(normalized_parts):
            return matched

    return None


def find_amount_candidates(
    words: list[dict[str, Any]],
    label_words: list[dict[str, Any]],
    vertical_tolerance: float = DEFAULT_VERTICAL_TOLERANCE,
) -> list[dict[str, Any]]:
    """Collect amount-looking tokens to the right of a label on the same row."""
    if not label_words:
        return []

    label_right = max(word["left"] + word["width"] for word in label_words)
    label_center = sum(
        word["top"] + word["height"] / 2 for word in label_words
    ) / len(label_words)

    candidates = []
    for word in words:
        normalized = normalize_amount_token(word["text"])
        if normalized is None or word["left"] <= label_right:
            continue

        center = word["top"] + word["height"] / 2
        if abs(center - label_center) > vertical_tolerance:
            continue

        candidates.append({**word, "normalized": normalized})

    return sorted(candidates, key=lambda item: item["left"])


def extract_field(
    words: list[dict[str, Any]],
    field: str,
) -> dict[str, Any]:
    label = find_label(words, FIELD_LABELS[field])

    if label is None:
        return {
            "field": field,
            "value": None,
            "status": "label_not_found",
            "candidates": [],
        }

    candidates = find_amount_candidates(words, label)

    if not candidates:
        return {
            "field": field,
            "value": None,
            "status": "amount_not_found",
            "label_confidence": min(word["confidence"] for word in label),
            "candidates": [],
        }

    # Do not concatenate split tokens such as 684 and 00 into 684.00.
    if len(candidates) > 1:
        return {
            "field": field,
            "value": None,
            "status": "multiple_amount_tokens_review",
            "label_confidence": min(word["confidence"] for word in label),
            "candidates": [
                {
                    "raw": item["text"],
                    "normalized_candidate": item["normalized"],
                    "confidence": item["confidence"],
                    "x": round(item["left"], 2),
                    "y": round(item["top"], 2),
                }
                for item in candidates
            ],
        }

    candidate = candidates[0]
    confidence = candidate["confidence"]
    status = "recognized" if confidence >= 85 else "needs_review"

    return {
        "field": field,
        "value": candidate["normalized"] if status == "recognized" else None,
        "proposed_value": candidate["normalized"],
        "raw_ocr_token": candidate["text"],
        "confidence": confidence,
        "label_confidence": min(word["confidence"] for word in label),
        "coordinates": {
            "x": round(candidate["left"], 2),
            "y": round(candidate["top"], 2),
        },
        "status": status,
        "candidates": [
            {
                "raw": candidate["text"],
                "normalized_candidate": candidate["normalized"],
                "confidence": confidence,
            }
        ],
    }


def interpret_sgst_crop_tokens(
    tokens: list[dict[str, Any]],
    label_confidence: float,
) -> dict[str, Any]:
    """Interpret SGST crop OCR tokens without joining separate tokens."""
    candidates = []
    for token in tokens:
        normalized = normalize_amount_token(token["text"])
        if normalized is not None:
            candidates.append(
                {
                    "raw": token["text"],
                    "normalized_candidate": normalized,
                    "confidence": token["confidence"],
                }
            )

    if not candidates:
        return {
            "field": "sgst",
            "value": None,
            "status": "amount_not_found",
            "label_confidence": label_confidence,
            "candidates": [],
        }

    if len(candidates) > 1:
        return {
            "field": "sgst",
            "value": None,
            "status": "multiple_amount_tokens_review",
            "label_confidence": label_confidence,
            "candidates": candidates,
        }

    candidate = candidates[0]
    confidence = candidate["confidence"]
    status = (
        "recognized"
        if confidence >= SGST_CROP_CONFIDENCE_THRESHOLD
        else "needs_review"
    )
    return {
        "field": "sgst",
        "value": candidate["normalized_candidate"] if status == "recognized" else None,
        "proposed_value": candidate["normalized_candidate"],
        "raw_ocr_token": candidate["raw"],
        "confidence": confidence,
        "label_confidence": label_confidence,
        "status": status,
        "candidates": candidates,
    }


def extract_sgst_crop_field(
    image: Any,
    label_words: list[dict[str, Any]],
) -> dict[str, Any]:
    """Read the sample's isolated SGST amount using CLAHE, 5x and PSM 6."""
    if not label_words:
        return {
            "field": "sgst",
            "value": None,
            "status": "label_not_found",
            "candidates": [],
        }

    left, top, right, bottom = SGST_AMOUNT_CROP
    crop = image[top:bottom, left:right]
    if crop.size == 0:
        raise ValueError(f"Invalid or empty SGST amount crop: {SGST_AMOUNT_CROP}")

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)
    enlarged = cv2.resize(
        enhanced,
        None,
        fx=SGST_CROP_SCALE,
        fy=SGST_CROP_SCALE,
        interpolation=cv2.INTER_CUBIC,
    )
    data = pytesseract.image_to_data(
        enlarged,
        lang="eng",
        config="--oem 3 --psm 6",
        output_type=Output.DICT,
    )

    tokens = []
    for raw_text, raw_confidence in zip(data["text"], data["conf"]):
        text = raw_text.strip()
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            continue
        if text and confidence >= 0:
            tokens.append({"text": text, "confidence": confidence})

    result = interpret_sgst_crop_tokens(
        tokens,
        label_confidence=min(word["confidence"] for word in label_words),
    )
    result["ocr_method"] = "CLAHE 5x PSM 6"
    result["crop"] = SGST_AMOUNT_CROP
    return result



def interpret_total_amount_crop_tokens(
    tokens: list[dict[str, Any]],
    label_confidence: float,
) -> dict[str, Any]:
    """Interpret isolated Total Amount OCR tokens without guessing or joining."""
    candidates = []
    for token in tokens:
        normalized = normalize_amount_token(token["text"])
        if normalized is not None:
            candidates.append(
                {
                    "raw": token["text"],
                    "normalized_candidate": normalized,
                    "confidence": token["confidence"],
                }
            )

    if not candidates:
        return {
            "field": "total",
            "value": None,
            "status": "amount_not_found",
            "label_confidence": label_confidence,
            "candidates": [],
        }

    if len(candidates) > 1:
        return {
            "field": "total",
            "value": None,
            "status": "multiple_amount_tokens_review",
            "label_confidence": label_confidence,
            "candidates": candidates,
        }

    candidate = candidates[0]
    confidence = candidate["confidence"]
    status = (
        "recognized"
        if confidence >= TOTAL_AMOUNT_CROP_CONFIDENCE_THRESHOLD
        else "needs_review"
    )
    return {
        "field": "total",
        "value": candidate["normalized_candidate"] if status == "recognized" else None,
        "proposed_value": candidate["normalized_candidate"],
        "raw_ocr_token": candidate["raw"],
        "confidence": confidence,
        "label_confidence": label_confidence,
        "status": status,
        "candidates": candidates,
    }


def extract_total_amount_crop_field(
    image: Any,
    label_words: list[dict[str, Any]],
) -> dict[str, Any]:
    """Read the sample Total Amount without the currency symbol, grayscale 3x PSM 6."""
    if not label_words:
        return {
            "field": "total",
            "value": None,
            "status": "label_not_found",
            "candidates": [],
        }

    left, top, right, bottom = TOTAL_AMOUNT_CROP
    crop = image[top:bottom, left:right]
    if crop.size == 0:
        raise ValueError(f"Invalid or empty Total Amount crop: {TOTAL_AMOUNT_CROP}")

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    enlarged = cv2.resize(
        gray,
        None,
        fx=TOTAL_AMOUNT_CROP_SCALE,
        fy=TOTAL_AMOUNT_CROP_SCALE,
        interpolation=cv2.INTER_CUBIC,
    )
    data = pytesseract.image_to_data(
        enlarged,
        lang="eng",
        config="--oem 3 --psm 6",
        output_type=Output.DICT,
    )

    tokens = []
    for raw_text, raw_confidence in zip(data["text"], data["conf"]):
        text = raw_text.strip()
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            continue
        if text and confidence >= 0:
            tokens.append({"text": text, "confidence": confidence})

    result = interpret_total_amount_crop_tokens(
        tokens,
        label_confidence=min(word["confidence"] for word in label_words),
    )
    result["ocr_method"] = "grayscale 3x PSM 6"
    result["crop"] = TOTAL_AMOUNT_CROP
    return result


def extract_receipt_fields(
    image: Any,
    regions: dict[str, tuple[int, int, int, int]] | None = None,
) -> dict[str, Any]:
    """Run configured OCR passes and retain review evidence."""
    selected_regions = regions or DEFAULT_REGIONS
    word_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
    results = {}

    for field, psm in FIELD_PSM.items():
        region_name = "payment_details" if field == "amount_paid" else "tax_and_total"
        cache_key = (region_name, psm)

        if cache_key not in word_cache:
            word_cache[cache_key] = extract_words(
                image,
                selected_regions[region_name],
                psm,
            )

        if field == "sgst":
            results[field] = extract_sgst_crop_field(
                image,
                find_label(word_cache[cache_key], FIELD_LABELS[field]),
            )
        elif field == "total":
            results[field] = extract_total_amount_crop_field(
                image,
                find_label(word_cache[cache_key], FIELD_LABELS[field]),
            )
        else:
            results[field] = extract_field(word_cache[cache_key], field)

    return results


def print_word_diagnostics(
    image: Any,
    regions: dict[str, tuple[int, int, int, int]] | None = None,
) -> None:
    selected_regions = regions or DEFAULT_REGIONS

    for region_name, coordinates in selected_regions.items():
        psms = (6, 11) if region_name == "tax_and_total" else (6,)
        for psm in psms:
            print("\n" + "=" * 58)
            print(f"{region_name.upper()} - PSM {psm} TEXT")
            print("=" * 58)
            print(read_region_text(image, coordinates, psm))

            words = extract_words(image, coordinates, psm)
            print(f"\n{region_name.upper()} - PSM {psm} WORD COORDINATES")
            for word in words:
                print(
                    f"{word['text']:<18} "
                    f"x={word['left']:7.2f} "
                    f"y={word['top']:7.2f} "
                    f"confidence={word['confidence']:5.1f}"
                )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Experimental coordinate-aware receipt OCR."
    )
    parser.add_argument(
        "image",
        type=Path,
        help="Path to the receipt image on your computer.",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Print OCR text and word coordinates for each configured region.",
    )
    args = parser.parse_args()

    configure_tesseract()

    image = cv2.imread(str(args.image))
    if image is None:
        raise FileNotFoundError(f"Could not read receipt image: {args.image}")

    print(f"Image: {args.image}")
    print(f"Dimensions: {image.shape[1]} x {image.shape[0]}")

    if args.diagnostics:
        print_word_diagnostics(image)

    results = extract_receipt_fields(image)

    print("\n" + "=" * 65)
    print("COORDINATE-AWARE RECEIPT EXTRACTION")
    print("=" * 65)

    for field, result in results.items():
        print(f"\n{field}:")
        print(f"  status: {result['status']}")
        print(f"  value: {result.get('value')}")
        if result.get("proposed_value") is not None:
            print(f"  proposed_value: {result['proposed_value']}")
        if result.get("confidence") is not None:
            print(f"  confidence: {result['confidence']:.1f}")
        if result.get("candidates"):
            print(f"  candidates: {result['candidates']}")

    print(
        "\nNote: this is an experimental tool. Values requiring review "
        "are deliberately not promoted to final values."
    )


if __name__ == "__main__":
    main()
