import os
import math
import shutil
from pathlib import Path

import pytesseract
from PIL import Image


def _resolve_tesseract() -> str | None:
    """Find Tesseract from configuration, PATH, or common Windows install."""
    configured = os.getenv("TESSERACT_CMD")
    if configured:
        return configured

    discovered = shutil.which("tesseract")
    if discovered:
        return discovered

    windows_default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if windows_default.is_file():
        return str(windows_default)

    return None


TESSERACT_CMD = _resolve_tesseract()


def _configure_tesseract() -> None:
    """Configure Tesseract only when OCR is requested, not at module import."""
    if not TESSERACT_CMD:
        raise RuntimeError(
            "Tesseract OCR was not found. Install Tesseract and add it to PATH, "
            "or set the TESSERACT_CMD environment variable."
        )

    if Path(TESSERACT_CMD).is_absolute() and not Path(TESSERACT_CMD).is_file():
        raise RuntimeError(
            f"Tesseract executable does not exist: {TESSERACT_CMD}"
        )

    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def extract_text_from_pil_image(image: Image.Image, languages: str | None = None) -> str:
    """OCR an in-memory image using configured Tesseract language packs."""
    _configure_tesseract()
    lang = languages or os.getenv("TESSERACT_LANGUAGES", "eng")
    return pytesseract.image_to_string(
        image, lang=lang, config="--oem 3 --psm 6"
    ).strip()


def extract_text(image_path: str | Path) -> str:
    """Extract complete text from a receipt image using Tesseract OCR."""
    _configure_tesseract()
    path = Path(image_path)

    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {path}")

    with Image.open(path) as image:
        return pytesseract.image_to_string(
            image,
            lang=os.getenv("TESSERACT_LANGUAGES", "eng"),
            config="--oem 3 --psm 6"
        ).strip()


def extract_text_with_confidence(image_path: str | Path) -> list[dict]:
    """Extract recognized words with confidence and bounding-box data."""
    _configure_tesseract()
    path = Path(image_path)

    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {path}")

    with Image.open(path) as image:
        data = pytesseract.image_to_data(
            image,
            lang="eng",
            config="--oem 3 --psm 6",
            output_type=pytesseract.Output.DICT
        )

    results = []
    for index, raw_word in enumerate(data["text"]):
        word = raw_word.strip()
        if not word:
            continue

        confidence = float(data["conf"][index])
        if confidence < 0:
            continue

        results.append({
            "word": word,
            "confidence": confidence,
            "left": data["left"][index],
            "top": data["top"][index],
            "width": data["width"][index],
            "height": data["height"][index]
        })

    return results


def extract_text_with_confidence_from_pil_image(
    image: Image.Image, languages: str | None = None
) -> dict:
    """Return OCR text and word-level confidence for an in-memory image.

    Tesseract confidence is a recognition signal, not a probability that
    extracted financial fields are correct.
    """
    _configure_tesseract()
    lang = languages or os.getenv("TESSERACT_LANGUAGES", "eng")
    config = "--oem 3 --psm 6"
    text = pytesseract.image_to_string(image, lang=lang, config=config).strip()
    data = pytesseract.image_to_data(
        image, lang=lang, config=config, output_type=pytesseract.Output.DICT
    )
    words = []
    for index, raw_word in enumerate(data["text"]):
        word = raw_word.strip()
        if not word:
            continue
        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            continue
        if not math.isfinite(confidence) or confidence < 0:
            continue
        words.append({
            "word": word,
            "confidence": confidence,
            "left": data["left"][index],
            "top": data["top"][index],
            "width": data["width"][index],
            "height": data["height"][index],
        })
    average = (
        round(sum(word["confidence"] for word in words) / len(words), 2)
        if words else None
    )
    return {"text": text, "words": words, "average_confidence": average}
