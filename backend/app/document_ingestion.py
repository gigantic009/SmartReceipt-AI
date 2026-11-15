"""Safe document text ingestion for images and text/scanned PDFs."""
from __future__ import annotations

import io
from pathlib import Path

import fitz
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.app.image_security import validate_image_dimensions
from backend.app.ocr_engine import extract_text_with_confidence_from_pil_image

MAX_PDF_PAGES = 25
MAX_IMAGE_PIXELS = 25_000_000


def _ocr_page(image: Image.Image, page_number: int) -> dict:
    result = extract_text_with_confidence_from_pil_image(image)
    return {
        "page": page_number,
        "text": result["text"],
        "method": "ocr",
        "average_confidence": result["average_confidence"],
        "word_count": len(result["words"]),
    }


def extract_document_text(data: bytes, filename: str) -> dict:
    """Extract per-page text from PDFs and supported raster images.

    Text-based PDFs use their embedded text. Scanned PDF pages and raster
    images use Tesseract and include word-level confidence summaries.
    """
    extension = Path(filename).suffix.lower()
    pages: list[dict] = []

    if extension == ".pdf":
        try:
            document = fitz.open(stream=data, filetype="pdf")
        except Exception as error:
            raise ValueError("The uploaded PDF could not be opened.") from error
        with document:
            if document.is_encrypted:
                raise ValueError("Password-protected PDFs are not supported.")
            if document.page_count < 1 or document.page_count > MAX_PDF_PAGES:
                raise ValueError(f"PDF must contain between 1 and {MAX_PDF_PAGES} pages.")
            for index, page in enumerate(document):
                text = page.get_text("text").strip()
                if text:
                    pages.append({
                        "page": index + 1,
                        "text": text,
                        "method": "embedded_text",
                        "average_confidence": None,
                        "word_count": len(text.split()),
                    })
                    continue
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                if pixmap.width * pixmap.height > MAX_IMAGE_PIXELS:
                    raise ValueError("A rendered PDF page exceeds the image pixel limit.")
                image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
                pages.append(_ocr_page(image, index + 1))

    elif extension in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
        try:
            with Image.open(io.BytesIO(data)) as source:
                expected = {
                    ".jpg": {"JPEG"}, ".jpeg": {"JPEG"}, ".png": {"PNG"},
                    ".webp": {"WEBP"}, ".tif": {"TIFF"}, ".tiff": {"TIFF"},
                }
                if source.format not in expected.get(extension, set()):
                    raise ValueError("The file extension does not match the image content.")
                width, height = source.size
                validate_image_dimensions(width, height)
                if width * height > MAX_IMAGE_PIXELS:
                    raise ValueError("Image exceeds the maximum pixel count.")
                image = ImageOps.exif_transpose(source).convert("RGB")
        except (UnidentifiedImageError, OSError) as error:
            raise ValueError("The uploaded file is not a valid image.") from error
        pages.append(_ocr_page(image, 1))
    else:
        raise ValueError("Supported formats are JPG, JPEG, PNG, WEBP, TIFF and PDF.")

    combined = "\n\n".join(
        f"[Page {page['page']}]\n{page['text']}"
        for page in pages if page["text"].strip()
    ).strip()
    confidence_pages = [
        page for page in pages
        if page["method"] == "ocr" and page["average_confidence"] is not None
    ]
    confidence_word_count = sum(page["word_count"] for page in confidence_pages)
    average_confidence = (
        round(
            sum(page["average_confidence"] * page["word_count"] for page in confidence_pages)
            / confidence_word_count,
            2,
        )
        if confidence_word_count else None
    )
    return {
        "text": combined,
        "pages": pages,
        "page_count": len(pages),
        "methods": sorted({page["method"] for page in pages}),
        "empty_pages": [page["page"] for page in pages if not page["text"].strip()],
        "average_confidence": average_confidence,
        "ocr_word_count": sum(
            page["word_count"] for page in pages if page["method"] == "ocr"
        ),
    }
