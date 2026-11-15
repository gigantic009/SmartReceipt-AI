"""Sweep Amount Paid crop boundaries to preserve every amount character.

Diagnostic only: no OCR reading is automatically accepted.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import pytesseract
from pytesseract import Output

from backend.app.coordinate_extractor import configure_tesseract


RIGHT, TOP, BOTTOM = 175, 258, 279
LEFT_EDGES = range(89, 100)
SCALES = (2, 3, 4)
PSM_MODES = (6, 7)
WHITELIST_CONFIG = "-c tessedit_char_whitelist=0123456789,."


def preprocess_variants(gray):
    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(4, 4),
    ).apply(gray)
    blurred = cv2.GaussianBlur(gray, (0, 0), 1.0)
    sharpened = cv2.addWeighted(gray, 1.6, blurred, -0.6, 0)
    return {
        "grayscale": gray,
        "clahe": clahe,
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
    scores = []
    for token, confidence in zip(data["text"], data["conf"]):
        token = token.strip()
        try:
            score = float(confidence)
        except (TypeError, ValueError):
            continue
        if token and score >= 0:
            tokens.append(token)
            scores.append(score)
    if not tokens:
        return "", 0.0
    return " ".join(tokens), sum(scores) / len(scores)


def run_experiment(image_path: Path) -> None:
    configure_tesseract()
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    print(f"Image: {image_path}")
    print(f"Image dimensions: {image.shape[1]} x {image.shape[0]}")
    print("Diagnostic only: no OCR reading is automatically accepted.")
    print("Sweeping crop left edge from x=89 through x=99.")
    print("A valid candidate must preserve the complete amount and decimal.")

    results = []
    for left in LEFT_EDGES:
        crop = image[TOP:BOTTOM, left:RIGHT]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        for prep_name, variant in preprocess_variants(gray).items():
            for scale in SCALES:
                enlarged = cv2.resize(
                    variant,
                    None,
                    fx=scale,
                    fy=scale,
                    interpolation=cv2.INTER_CUBIC,
                )
                for psm in PSM_MODES:
                    for whitelist_name, extra in (
                        ("normal", ""),
                        ("numeric_whitelist", WHITELIST_CONFIG),
                    ):
                        config = f"--oem 3 --psm {psm} {extra}".strip()
                        text, confidence = read_candidate(enlarged, config)
                        results.append({
                            "confidence": confidence,
                            "text": text or "<empty>",
                            "left": left,
                            "prep": prep_name,
                            "scale": scale,
                            "psm": psm,
                            "whitelist": whitelist_name,
                        })

    results.sort(key=lambda item: item["confidence"], reverse=True)
    print(f"\\nTested {len(results)} configurations.")
    print("Top 25 results:")
    for i, item in enumerate(results[:25], 1):
        print(
            f"{i:02d}. {item['confidence']:.1f}% | "
            f"text={item['text']!r} | left_x={item['left']} | "
            f"prep={item['prep']} | scale={item['scale']}x | "
            f"PSM={item['psm']} | {item['whitelist']}"
        )

    expected = {"12,390.00", "12390.00"}
    valid = [
        item for item in results
        if item["confidence"] >= 85 and item["text"].strip() in expected
    ]
    if valid:
        print("\\nComplete-amount candidates meeting 85%:")
        for item in valid[:10]:
            print(
                f"{item['confidence']:.1f}% | {item['text']} | "
                f"left_x={item['left']} | {item['prep']} | "
                f"{item['scale']}x | PSM={item['psm']}"
            )
    else:
        print(
            "\\nNo complete amount candidate reached 85%. "
            "Keep Amount Paid marked needs_review."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sweep Amount Paid crop left boundaries."
    )
    parser.add_argument("image", type=Path, help="Path to the local receipt image")
    args = parser.parse_args()
    run_experiment(args.image)


if __name__ == "__main__":
    main()
