"""Safe document text ingestion for images and text/scanned PDFs."""
from __future__ import annotations
import io
import os
from pathlib import Path

import fitz
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.app.image_security import validate_image_dimensions
from backend.app.ocr_engine import extract_text_from_pil_image

MAX_PDF_PAGES = 25
MAX_IMAGE_PIXELS = 25_000_000


def extract_document_text(data: bytes, filename: str) -> dict:
    """Extract per-page text from a PDF or raster image.

    PDFs use embedded text when present and OCR rendered pages otherwise.
    Page and pixel limits protect the local service from oversized documents.
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
                method = "embedded_text"
                if not text:
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    if pixmap.width * pixmap.height > MAX_IMAGE_PIXELS:
                        raise ValueError("A rendered PDF page exceeds the image pixel limit.")
                    image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
                    text = extract_text_from_pil_image(image)
                    method = "ocr"
                pages.append({"page": index + 1, "text": text, "method": method})
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
        pages.append({"page": 1, "text": extract_text_from_pil_image(image), "method": "ocr"})
    else:
        raise ValueError("Supported formats are JPG, JPEG, PNG, WEBP, TIFF and PDF.")

    combined = "\n\n".join(
        f"[Page {page['page']}]\n{page['text']}" for page in pages if page["text"].strip()
    ).strip()
    return {
        "text": combined,
        "pages": pages,
        "page_count": len(pages),
        "methods": sorted({page["method"] for page in pages}),
        "empty_pages": [page["page"] for page in pages if not page["text"].strip()],
    }
