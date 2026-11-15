import fitz
import pytest
from io import BytesIO
from PIL import Image

from backend.app.document_ingestion import extract_document_text


def make_pdf(*page_text: str) -> bytes:
    document = fitz.open()
    for text in page_text:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    payload = document.tobytes()
    document.close()
    return payload


def test_pdf_embedded_text_is_extracted_page_by_page():
    result = extract_document_text(
        make_pdf("Example Store Invoice 100.00", "Tax 5.00 Total 105.00"),
        "invoice.pdf",
    )
    assert result["page_count"] == 2
    assert result["methods"] == ["embedded_text"]
    assert "Example Store" in result["text"]
    assert "[Page 2]" in result["text"]
    assert result["average_confidence"] is None
    assert result["ocr_word_count"] == 0


def test_pdf_page_limit_is_enforced():
    pdf = make_pdf(*["page"] * 26)
    with pytest.raises(ValueError, match="between 1 and 25 pages"):
        extract_document_text(pdf, "large.pdf")


def test_unsupported_document_extension_is_rejected():
    with pytest.raises(ValueError, match="Supported formats"):
        extract_document_text(b"not a document", "notes.docx")


def test_scanned_pdf_reports_tesseract_confidence(monkeypatch):
    from backend.app import document_ingestion

    monkeypatch.setattr(
        document_ingestion,
        "extract_text_with_confidence_from_pil_image",
        lambda image: {
            "text": "Example Store Total 105.00",
            "words": [{"word": "Example", "confidence": 82.0}],
            "average_confidence": 82.0,
        },
    )
    result = extract_document_text(make_pdf(""), "scanned.pdf")
    assert result["methods"] == ["ocr"]
    assert result["average_confidence"] == 82.0
    assert result["ocr_word_count"] == 1
    assert result["pages"][0]["average_confidence"] == 82.0


def test_embedded_pdf_text_marks_confidence_not_applicable():
    result = extract_document_text(make_pdf("Text-based invoice 123.00"), "invoice.pdf")
    assert result["average_confidence"] is None
    assert result["ocr_word_count"] == 0
    assert result["pages"][0]["average_confidence"] is None


def test_image_ingestion_uses_confidence_aware_ocr(monkeypatch):
    from backend.app import document_ingestion

    output = BytesIO()
    Image.new("RGB", (80, 50), "white").save(output, format="PNG")
    monkeypatch.setattr(
        document_ingestion,
        "extract_text_with_confidence_from_pil_image",
        lambda image: {
            "text": "Store total 10.00",
            "words": [{"word": "Store", "confidence": 42.0}],
            "average_confidence": 42.0,
        },
    )
    result = extract_document_text(output.getvalue(), "receipt.png")
    assert result["average_confidence"] == 42.0
    assert result["ocr_word_count"] == 1
