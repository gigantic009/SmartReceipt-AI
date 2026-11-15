import fitz
import pytest

from backend.app.document_ingestion import extract_document_text


def make_pdf(*page_text: str) -> bytes:
    document = fitz.open()
    for text in page_text:
        page = document.new_page()
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


def test_pdf_page_limit_is_enforced():
    pdf = make_pdf(*["page"] * 26)
    with pytest.raises(ValueError, match="between 1 and 25 pages"):
        extract_document_text(pdf, "large.pdf")


def test_unsupported_document_extension_is_rejected():
    with pytest.raises(ValueError, match="Supported formats"):
        extract_document_text(b"not a document", "notes.docx")
