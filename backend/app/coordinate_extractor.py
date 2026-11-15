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
DEFAULT_VERTICAL_TOLERANCE = 12

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
