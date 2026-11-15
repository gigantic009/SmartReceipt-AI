"""Compare isolated Round Off crops and OCR settings.

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


# Coordinates are for the original 500x333 sample receipt.
# The first crop retains the printed minus sign; the second tests the amount
# without that leading mark. These are diagnostic candidate regions.
CROPS = {
    "with_leading_mark": (445, 250, 490, 263),
    "amount_only": (453, 250, 490, 263),
}
PSM_MODES = (6, 7, 8, 13)
SCALES = (3, 4, 5)
WHITELIST_CONFIG = "-c tessedit_char_whitelist=0123456789,."


def run_experiment(image_path: Path) -> None:
    configure_tesseract()
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    print(f"Image: {image_path}")
    print(f"Image dimensions: {image.shape[1]} x {image.shape[0]}")
    print("Diagnostic only: readings are evidence, not accepted financial values.")
    print("Numeric whitelist: digits, comma and decimal point only.")

    for crop_name, coordinates in CROPS.items():
        left, top, right, bottom = coordinates
        crop = image[top:bottom, left:right]
        if crop.size == 0:
            raise ValueError(f"Empty crop {crop_name}: {coordinates}")

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
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
        variants = {
            "grayscale": gray,
            "clahe": clahe,
            "otsu": otsu,
        }

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
                    for whitelist_name, extra_config in (
                        ("normal", ""),
                        ("numeric_whitelist", WHITELIST_CONFIG),
                    ):
                        config = f"--oem 3 --psm {psm} {extra_config}".strip()
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
                            f"\\n[{crop_name}, {variant_name}, {scale}x, "
                            f"PSM={psm}, {whitelist_name}]"
                            f"\\n  text: {text or '<empty>'}"
                            f"\\n  tokens: {', '.join(tokens) if tokens else '<none>'}"
                        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test isolated Round Off crops and OCR settings."
    )
    parser.add_argument("image", type=Path, help="Path to the local receipt image")
    args = parser.parse_args()
    run_experiment(args.image)


if __name__ == "__main__":
    main()
