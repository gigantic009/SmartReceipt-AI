from PIL import Image

from backend.app import ocr_engine


def test_in_memory_ocr_returns_words_and_average_confidence(monkeypatch):
    monkeypatch.setattr(ocr_engine, "_configure_tesseract", lambda: None)
    monkeypatch.setattr(
        ocr_engine.pytesseract,
        "image_to_string",
        lambda image, lang, config: "Hello World",
    )
    monkeypatch.setattr(
        ocr_engine.pytesseract,
        "image_to_data",
        lambda image, lang, config, output_type: {
            "text": ["Hello", "World", ""],
            "conf": ["80", "60", "-1"],
            "left": [1, 2, 0],
            "top": [3, 4, 0],
            "width": [5, 6, 0],
            "height": [7, 8, 0],
        },
    )
    result = ocr_engine.extract_text_with_confidence_from_pil_image(
        Image.new("RGB", (20, 20), "white")
    )
    assert result["text"] == "Hello World"
    assert result["average_confidence"] == 70.0
    assert [word["word"] for word in result["words"]] == ["Hello", "World"]


def test_in_memory_ocr_confidence_is_none_when_no_words(monkeypatch):
    monkeypatch.setattr(ocr_engine, "_configure_tesseract", lambda: None)
    monkeypatch.setattr(
        ocr_engine.pytesseract,
        "image_to_string",
        lambda image, lang, config: "",
    )
    monkeypatch.setattr(
        ocr_engine.pytesseract,
        "image_to_data",
        lambda image, lang, config, output_type: {
            "text": ["", "noise"],
            "conf": ["-1", "nan"],
            "left": [0, 0],
            "top": [0, 0],
            "width": [0, 0],
            "height": [0, 0],
        },
    )
    result = ocr_engine.extract_text_with_confidence_from_pil_image(
        Image.new("RGB", (20, 20), "white")
    )
    assert result["words"] == []
    assert result["average_confidence"] is None
