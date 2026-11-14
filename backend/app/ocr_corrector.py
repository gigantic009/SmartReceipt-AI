
import re
from decimal import Decimal, InvalidOperation

# Common OCR corrections for receipt terminology
COMMON_CORRECTIONS = {
    "oty": "Qty",
    "seevice": "Service",
    "up!": "UPI",
    "mateh": "Match",
    "tess": "less"
}


def correct_word(word: str) -> dict:
    """
    Correct common OCR mistakes.

    Returns the original word, corrected word,
    and whether a correction was applied.
    """

    normalized_word = word.strip()
    lookup_word = normalized_word.lower()

    corrected_word = COMMON_CORRECTIONS.get(
        lookup_word,
        normalized_word
    )

    return {
        "original": normalized_word,
        "corrected": corrected_word,
        "was_corrected": corrected_word != normalized_word
    }


def check_confidence(confidence: float) -> dict:
    """
    Classify OCR confidence and determine
    whether manual review is required.
    """

    if confidence >= 85:
        status = "high"
        review_required = False

    elif confidence >= 60:
        status = "medium"
        review_required = True

    else:
        status = "low"
        review_required = True

    return {
        "confidence": confidence,
        "status": status,
        "review_required": review_required
    }

def normalize_amount(amount: str) -> dict:
    """
    Normalize monetary formatting without guessing
    ambiguous values.
    """

    original = amount.strip()
    cleaned = original.replace("₹", "").replace("INR", "").strip()

    # Handle values such as 850,00 and 171,25.
    # A comma followed by exactly two digits is
    # treated as a decimal separator only when
    # there is no decimal point.
    if "." not in cleaned and re.fullmatch(
        r"\d+,\d{2}", cleaned
    ):
        cleaned = cleaned.replace(",", ".")

    # Handle standard comma-separated thousands:
    # 6,850.00 -> 6850.00
    elif re.fullmatch(
        r"\d{1,3}(,\d{3})+(\.\d{2})?", cleaned
    ):
        cleaned = cleaned.replace(",", "")

    try:
        value = Decimal(cleaned)

        if not value.is_finite() or value < 0:
            raise InvalidOperation

        normalized = f"{value:.2f}"

        return {
            "original": original,
            "normalized": normalized,
            "was_corrected": original != normalized,
            "valid": True
        }

    except InvalidOperation:
        return {
            "original": original,
            "normalized": None,
            "was_corrected": False,
            "valid": False
        }

if __name__ == "__main__":

    test_words = [
        "Oty",
        "Seevice",
        "UP!",
        "Mateh",
        "Example",
        "Garden"
    ]

    print("\n===== OCR CORRECTION TEST =====\n")

    for word in test_words:

        result = correct_word(word)

        print(
            f"Original: {result['original']:<12} "
            f"Corrected: {result['corrected']:<12} "
            f"Changed: {result['was_corrected']}"
        )
    print("\n===== CONFIDENCE TEST =====\n")

    for score in [96, 72, 42]:
        print(check_confidence(score))

    print("\n===== AMOUNT NORMALIZATION TEST =====\n")

    test_amounts = [
        "850,00",
        "171,25",
        "6,850.00",
        "7,192.50",
        "2000"
    ]

    for amount in test_amounts:
        print(normalize_amount(amount))
    print("\n===============================\n")
