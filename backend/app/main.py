from pathlib import Path
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError

from backend.app.database import save_receipt
from backend.app.image_security import validate_image_dimensions
from backend.app.image_processor import (
    PreprocessConfig,
    load_image,
    preprocess_receipt,
    save_image
)
from backend.app.ocr_engine import extract_text, extract_text_with_confidence
from backend.app.receipt_parser import parse_receipt, validate_parsed_receipt
from backend.app.global_billing import parse_global_document, validate_global_document


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "backend" / "uploads"
OCR_READY_DIR = PROJECT_ROOT / "backend" / "ocr_ready"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_FORMATS = {
    "JPEG": {".jpg", ".jpeg"},
    "PNG": {".png"}
}

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OCR_READY_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="SmartReceipt AI",
    description="AI-powered receipt scanning and expense management API",
    version="0.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "message": "Welcome to SmartReceipt AI!",
        "status": "API is running"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/upload-receipt")
async def upload_receipt(file: UploadFile = File(...)):
    """Validate, store, preprocess, OCR, parse, and validate one receipt."""
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, JPEG and PNG files are allowed."
        )

    receipt_id = str(uuid.uuid4())
    upload_path = UPLOAD_DIR / f"{receipt_id}{extension}"
    processed_path = OCR_READY_DIR / f"{receipt_id}.png"

    try:
        size = 0
        with upload_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Receipt image must be 10 MB or smaller."
                    )
                destination.write(chunk)

        if size == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")

        try:
            with Image.open(upload_path) as image:
                image_format = image.format
                width, height = image.size
                validate_image_dimensions(width, height)
                image.verify()
        except ValueError as error:
            raise HTTPException(status_code=413, detail=str(error)) from error
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is not a valid image."
            )

        if image_format not in ALLOWED_FORMATS:
            raise HTTPException(
                status_code=400,
                detail="The image content must be JPEG or PNG."
            )

        if extension not in ALLOWED_FORMATS[image_format]:
            raise HTTPException(
                status_code=400,
                detail="The file extension does not match the image content."
            )

        original_image = load_image(upload_path)
        processed_image = preprocess_receipt(
            original_image,
            PreprocessConfig()
        )
        save_image(processed_path, processed_image)

        ocr_text = extract_text(processed_path)
        if not ocr_text.strip():
            raise HTTPException(
                status_code=422,
                detail="No readable text was detected in this receipt."
            )

        parsed_receipt = parse_receipt(ocr_text)
        validation = validate_parsed_receipt(parsed_receipt)
        global_document = parse_global_document(ocr_text)
        global_validation = validate_global_document(global_document)

        confidence_items = extract_text_with_confidence(processed_path)
        average_confidence = (
            round(
                sum(item["confidence"] for item in confidence_items)
                / len(confidence_items),
                2
            )
            if confidence_items
            else None
        )

        review_required = (
            global_validation["status"] != "valid"
            or average_confidence is None
            or average_confidence < 85
        )
        response_status = "review_required" if review_required else "success"
        ocr_summary = {
            "average_confidence": average_confidence,
            "word_count": len(confidence_items),
            "review_required": review_required
        }

        save_receipt(
            receipt_id=receipt_id,
            original_filename=upload_path.name,
            processed_filename=processed_path.name,
            status=response_status,
            ocr_text=ocr_text,
            receipt=parsed_receipt,
            validation=validation,
            ocr=ocr_summary,
        )

        return {
            "message": "Receipt processed successfully.",
            "status": response_status,
            "receipt_id": receipt_id,
            "filename": upload_path.name,
            "processed_filename": processed_path.name,
            "ocr_text": ocr_text,
            "receipt": parsed_receipt,
            "global": global_document,
            "global_validation": global_validation,
            "validation": validation,
            "ocr": ocr_summary
        }

    except HTTPException:
        for path in (upload_path, processed_path):
            path.unlink(missing_ok=True)
        raise
    except (RuntimeError, FileNotFoundError) as error:
        for path in (upload_path, processed_path):
            path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=503,
            detail="Receipt processing is temporarily unavailable. Check the server configuration and logs."
        ) from error
    except Exception as error:
        for path in (upload_path, processed_path):
            path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing the receipt."
        ) from error
    finally:
        await file.close()
