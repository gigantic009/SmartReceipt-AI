"""Isolated Total Amount OCR experiment for the sample receipt.

This script is diagnostic only. It does not modify the production pipeline or
combine OCR tokens into financial values.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import pytesseract
from pytesseract import Output

from backend.app.coordinate_extractor import configure_tesseract


# Original-image coordinates for the Total Amount value on the 500x333 sample.
# The crop is based on the previously observed value position (around x=437,
# y=269). Adjust these only when testing a different receipt template.
TOTAL_AMOUNT_CROP = (420, 258, 490, 280)
PSM_MODES = (6, 7, 8, 11, 13)
SCALES = (3, 4, 5)


def run_experiment(image_path: Path) -> None:
    configure_tesseract()
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    left, top, right, bottom = TOTAL_AMOUNT_CROP
    crop = image[top:bottom, left:right]
    if crop.size == 0:
        raise ValueError(f"Empty Total Amount crop: {TOTAL_AMOUNT_CROP}")

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(gray)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    variants = {
        "grayscale": gray,
        "clahe": clahe,
        "otsu": otsu,
    }

    print(f"Image: {image_path}")
    print(f"Image dimensions: {image.shape[1]} x {image.shape[0]}")
    print(f"Total Amount crop: {TOTAL_AMOUNT_CROP}")
    print("Diagnostic only: OCR tokens will not be merged or accepted automatically.")

    for variant_name, variant in variants.items():
        for scale in SCALES:
            enlarged = cv2.resize(
                variant,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC,
            )
            for psm in PSM_MODES:
                config = f"--oem 3 --psm {psm}"
                text = pytesseract.image_to_string(
                    enlarged,
                    lang="eng",
                    config=config,
                ).strip().replace("\\n", " | ")

                data = pytesseract.image_to_data(
                    enlarged,
                    lang="eng",
                    config=config,
                    output_type=Output.DICT,
                )
                tokens = []
                for token, confidence in zip(data["text"], data["conf"]):
                    token = token.strip()
                    try:
                        score = float(confidence)
                    except (TypeError, ValueError):
                        continue
                    if token and score >= 0:
                        tokens.append(f"{token!r} ({score:.0f}%)")

                print(
                    f"\\n[{variant_name}, scale={scale}x, PSM={psm}]"
                    f"\\n  text: {text or '<empty>'}"
                    f"\\n  tokens: {', '.join(tokens) if tokens else '<none>'}"
                )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare OCR settings on the isolated Total Amount crop."
    )
    parser.add_argument("image", type=Path, help="Path to the local receipt image")
    args = parser.parse_args()
    run_experiment(args.image)


if __name__ == "__main__":
    main()
