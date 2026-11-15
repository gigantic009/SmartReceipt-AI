from pathlib import Path
import uuid
import hashlib
import csv
import io
import re
import sqlite3
from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, File, HTTPException, UploadFile, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError

from backend.app.database import (save_receipt, list_receipts, get_receipt, update_receipt, delete_receipt, find_duplicate, get_analytics, add_receipt_event, get_receipt_events, create_expense, list_expenses, delete_expense, create_vendor, list_vendors, create_budget, list_budgets, get_budget_status, get_vendor_by_name)
from backend.app.expense_intelligence import suggest_category
from backend.app.ai_enrichment import enrich_with_local_model
from backend.app.document_ingestion import extract_document_text
from backend.app.reporting import build_financial_workbook, build_financial_pdf
from backend.app.financial_assistant import answer_financial_question
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
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
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


def _suggest_document_category(document: dict, ocr_text: str) -> dict:
    merchant = document.get("merchant_name_candidate")
    vendor = get_vendor_by_name(merchant)
    if vendor and vendor.get("default_category"):
        return {"category": vendor["default_category"], "confidence": "medium", "method": "vendor_rule", "vendor_id": vendor["vendor_id"]}
    return suggest_category(merchant, ocr_text)


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
        digest = hashlib.sha256()
        with upload_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Receipt image must be 10 MB or smaller."
                    )
                destination.write(chunk)
                digest.update(chunk)

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
        global_document = enrich_with_local_model(global_document, ocr_text)
        global_validation = validate_global_document(global_document)
        category = _suggest_document_category(global_document, ocr_text)
        global_document["category"] = category["category"]
        global_document["category_suggestion"] = category
        duplicate = find_duplicate(digest.hexdigest())

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
            global_document=global_document,
            content_sha256=digest.hexdigest(),
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
            "ocr": ocr_summary,
            "duplicate": {"detected": duplicate is not None, "match": duplicate},
            "category": category,
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
 
@app.get("/receipts")
def receipts_list(
    search: str | None = None,
    status: str | None = None,
    category: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List saved documents with optional search and review filters."""
    return {"items": list_receipts(search=search, status=status, category=category, limit=limit, offset=offset)}


@app.get("/receipts/{receipt_id}")
def receipt_detail(receipt_id: str):
    record = get_receipt(receipt_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    return record


@app.patch("/receipts/{receipt_id}")
def receipt_update(receipt_id: str, fields: dict):
    """Save user corrections to normalized review fields."""
    allowed = {"merchant_name", "document_date", "total_amount", "currency_code", "category", "review_notes", "status"}
    if not fields or not set(fields).issubset(allowed):
        raise HTTPException(status_code=400, detail="Only supported review fields may be updated.")
    if "status" in fields and fields["status"] not in {"review_required", "success"}:
        raise HTTPException(status_code=400, detail="Invalid receipt status.")
    before = get_receipt(receipt_id)
    if before is None or not update_receipt(receipt_id, fields):
        raise HTTPException(status_code=404, detail="Receipt not found or no supported fields supplied.")
    add_receipt_event(receipt_id, "fields_corrected", {"before": {k: before.get(k) for k in fields}, "after": fields})
    return get_receipt(receipt_id)


@app.delete("/receipts/{receipt_id}")
def receipt_delete(receipt_id: str):
    record = get_receipt(receipt_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    add_receipt_event(receipt_id, "document_deleted", {"filename": record.get("original_filename")})
    delete_receipt(receipt_id)
    for folder, key in ((UPLOAD_DIR, "original_filename"), (OCR_READY_DIR, "processed_filename")):
        filename = Path(record.get(key) or "").name
        if filename:
            (folder / filename).unlink(missing_ok=True)
    return {"deleted": True, "receipt_id": receipt_id}


@app.get("/analytics")
def analytics():
    """Return currency-separated spend totals and category/month breakdowns."""
    return get_analytics()


@app.get("/exports/receipts.csv")
def export_receipts_csv():
    """Export the saved receipt register as CSV."""
    records = list_receipts(limit=500)
    output = io.StringIO()
    fields = ["receipt_id", "merchant_name", "document_date", "total_amount",
              "currency_code", "category", "status", "created_at"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        safe_record = {}
        for key, value in record.items():
            if key in fields and isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                value = "'" + value
            safe_record[key] = value
        writer.writerow(safe_record)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=smartreceipt-documents.csv"},
    )

async def _process_document_upload(file: UploadFile) -> dict:
    """Shared safe processing path for PDF, multipage and image uploads."""
    filename = Path(file.filename or "document").name
    extension = Path(filename).suffix.lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".pdf"}
    if extension not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported document format.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Document must be 10 MB or smaller.")

    digest = hashlib.sha256(data).hexdigest()
    duplicate = find_duplicate(digest)
    receipt_id = str(uuid.uuid4())
    stored_name = f"{receipt_id}{extension}"
    upload_path = UPLOAD_DIR / stored_name
    upload_path.write_bytes(data)
    try:
        try:
            extraction = extract_document_text(data, filename)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        ocr_text = extraction["text"]
        if not ocr_text:
            raise HTTPException(status_code=422, detail="No readable text was detected.")
        parsed = parse_receipt(ocr_text)
        legacy_validation = validate_parsed_receipt(parsed)
        document = parse_global_document(ocr_text)
        document = enrich_with_local_model(document, ocr_text)
        document["page_count"] = extraction["page_count"]
        document["page_extraction"] = [
            {"page": p["page"], "method": p["method"], "text_length": len(p["text"])}
            for p in extraction["pages"]
        ]
        category = _suggest_document_category(document, ocr_text)
        document["category"] = category["category"]
        document["category_suggestion"] = category
        validation = validate_global_document(document)
        review_required = validation["status"] != "valid" or duplicate is not None
        status = "review_required" if review_required else "success"
        ocr_summary = {
            "average_confidence": None,
            "word_count": len(ocr_text.split()),
            "review_required": review_required,
            "page_count": extraction["page_count"],
            "extraction_methods": extraction["methods"],
            "empty_pages": extraction["empty_pages"],
        }
        save_receipt(
            receipt_id=receipt_id,
            original_filename=stored_name,
            processed_filename=stored_name,
            status=status,
            ocr_text=ocr_text,
            receipt=parsed,
            validation=legacy_validation,
            ocr=ocr_summary,
            global_document=document,
            content_sha256=digest,
        )
        return {
            "message": "Document processed successfully.",
            "status": status,
            "receipt_id": receipt_id,
            "filename": stored_name,
            "ocr_text": ocr_text,
            "receipt": parsed,
            "global": document,
            "global_validation": validation,
            "validation": legacy_validation,
            "ocr": ocr_summary,
            "duplicate": {"detected": duplicate is not None, "match": duplicate},
            "category": category,
        }
    except Exception:
        upload_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@app.post("/upload-document")
async def upload_document(file: UploadFile = File(...)):
    """Upload a PDF, multipage scan or supported image."""
    return await _process_document_upload(file)


@app.post("/upload-batch")
async def upload_batch(files: list[UploadFile] = File(...)):
    """Process a small batch sequentially to keep local resource use bounded."""
    if not files or len(files) > 10:
        raise HTTPException(status_code=400, detail="Upload between 1 and 10 documents per batch.")
    results = []
    for file in files:
        try:
            results.append(await _process_document_upload(file))
        except HTTPException as error:
            results.append({
                "filename": Path(file.filename or "document").name,
                "status": "failed",
                "error": error.detail,
            })
        except Exception:
            results.append({
                "filename": Path(file.filename or "document").name,
                "status": "failed",
                "error": "Unexpected processing error. Check the backend logs.",
            })
    return {
        "processed": sum(1 for item in results if item.get("receipt_id")),
        "failed": sum(1 for item in results if item.get("status") == "failed"),
        "items": results,
    }

@app.get("/receipts/{receipt_id}/events")
def receipt_events(receipt_id: str):
    if get_receipt(receipt_id) is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    return {"items": get_receipt_events(receipt_id)}


@app.get("/expenses")
def expenses_list(currency_code: str | None = None, category: str | None = None):
    return {"items": list_expenses(currency_code=currency_code, category=category)}


@app.post("/expenses")
def expense_create(data: dict):
    required = {"description", "amount", "currency_code"}
    if not required.issubset(data):
        raise HTTPException(status_code=400, detail="description, amount and currency_code are required.")
    try:
        amount = Decimal(str(data["amount"]))
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="amount must be a valid decimal number.")
    if not amount.is_finite() or amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than zero.")
    currency = str(data["currency_code"]).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise HTTPException(status_code=400, detail="currency_code must be a three-letter currency code.")
    if not str(data["description"]).strip():
        raise HTTPException(status_code=400, detail="description cannot be empty.")
    normalized = {**data, "amount": format(amount, "f"), "currency_code": currency}
    try:
        return create_expense(normalized)
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="Expense could not be saved.") from error


@app.delete("/expenses/{expense_id}")
def expense_delete(expense_id: str):
    if not delete_expense(expense_id):
        raise HTTPException(status_code=404, detail="Expense not found.")
    return {"deleted": True, "expense_id": expense_id}


@app.get("/vendors")
def vendors_list():
    return {"items": list_vendors()}


@app.post("/vendors")
def vendor_create(data: dict):
    if not str(data.get("name", "")).strip():
        raise HTTPException(status_code=400, detail="Vendor name is required.")
    try:
        return create_vendor(data)
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="A vendor with this name already exists.") from error


@app.get("/budgets/status")
def budgets_status():
    return {"items": get_budget_status()}


@app.get("/budgets")
def budgets_list():
    return {"items": list_budgets()}


@app.post("/budgets")
def budget_create(data: dict):
    if not str(data.get("name", "")).strip() or not data.get("currency_code") or data.get("amount") is None:
        raise HTTPException(status_code=400, detail="name, amount and currency_code are required.")
    try:
        amount = Decimal(str(data["amount"]))
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="amount must be a valid decimal number.")
    if not amount.is_finite() or amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than zero.")
    currency = str(data["currency_code"]).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise HTTPException(status_code=400, detail="currency_code must be a three-letter currency code.")
    if data.get("period", "monthly") not in {"weekly", "monthly", "quarterly", "yearly"}:
        raise HTTPException(status_code=400, detail="period must be weekly, monthly, quarterly or yearly.")
    return create_budget({**data, "amount": format(amount, "f"), "currency_code": currency})

@app.get("/exports/finance.xlsx")
def export_finance_workbook():
    return StreamingResponse(
        iter([build_financial_workbook()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=smartreceipt-financial-report.xlsx"},
    )


@app.get("/reports/summary.pdf")
def export_financial_pdf():
    return StreamingResponse(
        iter([build_financial_pdf()]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=smartreceipt-financial-summary.pdf"},
    )

@app.post("/assistant/query")
def assistant_query(data: dict):
    question = data.get("question")
    if not isinstance(question, str) or not question.strip():
        raise HTTPException(status_code=400, detail="question must be a non-empty string.")
    if len(question) > 1000:
        raise HTTPException(status_code=400, detail="question must be 1000 characters or fewer.")
    return answer_financial_question(question)

