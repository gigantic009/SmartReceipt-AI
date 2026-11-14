
from pathlib import Path

import pytesseract
from PIL import Image


# Locate the Tesseract executable
TESSERACT_PATH = Path(
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# Configure pytesseract
if not TESSERACT_PATH.exists():
    raise FileNotFoundError(
        f"Tesseract executable not found: {TESSERACT_PATH}"
    )

pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_PATH)


def extract_text(image_path: str) -> str:
    """
    Extract text from a receipt image using Tesseract OCR.
    """

    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    with Image.open(image_path) as image:

        # OCR configuration
        config = "--oem 3 --psm 6"

        extracted_text = pytesseract.image_to_string(
            image,
            lang="eng",
            config=config
        )

    return extracted_text.strip()
def extract_text_with_confidence(image_path: str):
    """
    Extract words along with their OCR confidence scores.
    """

    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    with Image.open(image_path) as image:

        config = "--oem 3 --psm 6"

        data = pytesseract.image_to_data(
            image,
            lang="eng",
            config=config,
            output_type=pytesseract.Output.DICT
        )

    results = []

    for i, word in enumerate(data["text"]):

        word = word.strip()

        if not word:
            continue

        confidence = float(data["conf"][i])

        if confidence < 0:
            continue

        results.append({
            "word": word,
            "confidence": confidence,
            "left": data["left"][i],
            "top": data["top"][i],
            "width": data["width"][i],
            "height": data["height"][i]
        })

    return results

if __name__ == "__main__":

    receipt_path = (
        "backend/ocr_ready/"
        "12cfe97d-46fb-45fa-b618-1c18795271ba.png"
    )

    # Test 1: Extract complete text
    text = extract_text(receipt_path)

    print("\n========== OCR RESULT ==========\n")
    print(text)

    # Test 2: Extract words with confidence scores
    results = extract_text_with_confidence(receipt_path)

    print("\n====== OCR CONFIDENCE SCORES ======\n")

    for item in results:
        print(
            f"Word: {item['word']:<20} "
            f"Confidence: {item['confidence']:>6.2f}%"
        )

    print("\n===================================")