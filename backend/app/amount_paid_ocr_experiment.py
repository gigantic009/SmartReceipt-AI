"""Compare Amount Paid crop boundaries and OCR settings.

Diagnostic only: this script never changes the production extractor and
never accepts or combines OCR readings automatically.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import pytesseract
from pytesseract import Output

from backend.app.coordinate_extractor import configure_tesseract


# Candidate coordinates for the original 500x333 sample receipt.
# The printed amount starts near x=86, y=267. Compare retaining and
# excluding the noisy leading marker while keeping the full amount visible.
CROPS = {
    "wide_context": (72, 254, 175, 281),
    "with_leading_marker": (78, 258, 170, 278),
    "amount_only": (88, 258, 170, 278),
}
PSM_MODES = (6, 7, 8, 13)
SCALES = (2, 3, 4, 5)
WHITELIST_CONFIG = "-c tessedit_char_whitelist=0123456789,."


def preprocess_variants(gray):
    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(4, 4),
    ).apply(gray)

    _, otsu = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    adaptive = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2,
    )

    blurred = cv2.GaussianBlur(gray, (0, 0), 1.0)
    sharpened = cv2.addWeighted(gray, 1.6, blurred, -0.6, 0)

    return {
        "grayscale": gray,
        "clahe": clahe,
        "otsu": otsu,
        "adaptive": adaptive,
        "sharpened": sharpened,
    }


def read_candidate(image, config):
    data = pytesseract.image_to_data(
        image,
        lang="eng",
        config=config,
        output_type=Output.DICT,
    )

    tokens = []
    confidences = []
    for token, confidence in zip(data["text"], data["conf"]):
        token = token.strip()
        try:
            score = float(confidence)
        except (TypeError, ValueError):
            continue
        if token and score >= 0:
            tokens.append(token)
            confidences.append(score)

    if not tokens:
        return "", 0.0

    return " ".join(tokens), sum(confidences) / len(confidences)


def run_experiment(image_path: Path) -> None:
    configure_tesseract()
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    print(f"Image: {image_path}")
    print(f"Image dimensions: {image.shape[1]} x {image.shape[0]}")
    print("Diagnostic only: no OCR value is automatically accepted.")
    print("Numeric whitelist: digits, comma and decimal point only.")

    results = []

    for crop_name, coordinates in CROPS.items():
        left, top, right, bottom = coordinates
        crop = image[top:bottom, left:right]
        if crop.size == 0:
            raise ValueError(f"Empty crop {crop_name}: {coordinates}")

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        for variant_name, variant in preprocess_variants(gray).items():
            for scale in SCALES:
                enlarged = cv2.resize(
                    variant,
                    None,
                    fx=scale,
                    fy=scale,
                    interpolation=cv2.INTER_CUBIC,
                )

                for psm in PSM_MODES:
                    for whitelist_name, extra_config in (
                        ("normal", ""),
                        ("numeric_whitelist", WHITELIST_CONFIG),
                    ):
                        config = f"--oem 3 --psm {psm} {extra_config}".strip()
                        text, confidence = read_candidate(enlarged, config)

                        results.append({
                            "confidence": confidence,
                            "text": text or "<empty>",
                            "crop": crop_name,
                            "coordinates": coordinates,
                            "preprocessing": variant_name,
                            "scale": scale,
                            "psm": psm,
                            "whitelist": whitelist_name,
                        })

    results.sort(key=lambda item: item["confidence"], reverse=True)

    print(f"\\nTested {len(results)} configurations.")
    print("Top 20 results by OCR confidence:")
    for index, result in enumerate(results[:20], start=1):
        print(
            f"{index:02d}. {result['confidence']:.1f}% | "
            f"text={result['text']!r} | "
            f"crop={result['crop']} {result['coordinates']} | "
            f"prep={result['preprocessing']} | "
            f"scale={result['scale']}x | "
            f"PSM={result['psm']} | "
            f"{result['whitelist']}"
        )

    expected = {"12,390.00", "12390.00"}
    accepted = [
        item for item in results
        if item["confidence"] >= 85
        and item["text"].strip() in expected
    ]
    if accepted:
        print("\\nCandidates meeting the 85% threshold and expected amount format:")
        for item in accepted[:10]:
            print(
                f"{item['confidence']:.1f}% | {item['text']} | "
                f"{item['crop']} | {item['preprocessing']} | "
                f"{item['scale']}x | PSM={item['psm']}"
            )
    else:
        print(
            "\\nNo candidate reached 85% with the expected amount format. "
            "Keep Amount Paid marked needs_review."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare Amount Paid crop boundaries and OCR preprocessing."
    )
    parser.add_argument("image", type=Path, help="Path to the local receipt image")
    args = parser.parse_args()
    run_experiment(args.image)


if __name__ == "__main__":
    main()
