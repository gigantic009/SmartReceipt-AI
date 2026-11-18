from pathlib import Path
import hashlib
import csv
import io
import json
import logging
import os
import re
import uuid

from fastapi import Body, Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from backend.app.auth import verify_password
from backend.app.database import (
    DEFAULT_DATABASE_PATH,
    auth_is_blocked,
    clear_auth_failures,
    create_session,
    create_user,
    delete_receipt,
    find_user_by_email,
    get_receipt,
    get_session_user,
    initialize_database,
    list_receipts,
    list_sessions,
    revoke_all_sessions,
    list_review_events,
    list_reconciliation_receipts,
    record_auth_failure,
    revoke_session,
    review_receipt,
    save_receipt,
)
from backend.app.image_security import validate_image_dimensions
from backend.app.image_processor import (
    PreprocessConfig,
    load_image,
    preprocess_receipt,
    save_image,
)
from backend.app.ocr_engine import extract_text, extract_text_with_confidence
from backend.app.receipt_parser import normalize_receipt_amount, validate_parsed_receipt
from backend.app.structured_extractor import extract_receipt_fields
from backend.app.reconciliation import suggest_matches

logger = logging.getLogger("smartreceipt")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = Path(os.getenv("SMARTRECEIPT_DB_PATH", str(DEFAULT_DATABASE_PATH))).expanduser()
UPLOAD_DIR = Path(os.getenv("SMARTRECEIPT_UPLOAD_DIR", str(PROJECT_ROOT / "backend" / "uploads"))).expanduser()
OCR_READY_DIR = Path(os.getenv("SMARTRECEIPT_OCR_READY_DIR", str(PROJECT_ROOT / "backend" / "ocr_ready"))).expanduser()
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PAGE_SIZE = 50
SESSION_SECONDS = 7 * 24 * 60 * 60
ALLOWED_FORMATS = {"JPEG": {".jpg", ".jpeg"}, "PNG": {".png"}}
REVIEW_FIELDS = {"merchant", "date", "subtotal", "tax", "total", "currency", "payment_method"}

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OCR_READY_DIR.mkdir(parents=True, exist_ok=True)
initialize_database(DATABASE_PATH)

app = FastAPI(
    title="SmartReceipt AI",
    description="Private receipt capture, OCR extraction, financial validation, and auditable human review.",
    version="1.0.0",
)


def _session_cookie_options():
    return {
        "httponly": True,
        "secure": os.getenv("COOKIE_SECURE", "false").lower() == "true" or os.getenv("ENVIRONMENT") == "production",
        "samesite": "strict",
        "path": "/",
        "max_age": SESSION_SECONDS,
    }


def get_current_user(request: Request) -> dict:
    user = get_session_user(request.cookies.get("sr_session"), DATABASE_PATH)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def _auth_attempt_key(request: Request, email: str) -> str:
    client_ip = request.client.host if request.client else "unknown"
    return hashlib.sha256((client_ip + "|" + email.lower()).encode("utf-8")).hexdigest()


def _safe_stored_path(directory: Path, filename: str) -> Path:
    if not filename or Path(filename).name != filename:
        raise HTTPException(status_code=404, detail="Stored file not found.")
    root = directory.resolve()
    target = (root / filename).resolve()
    if target.parent != root:
        raise HTTPException(status_code=404, detail="Stored file not found.")
    return target



@app.middleware("http")
async def same_origin_state_change_guard(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin:
            from urllib.parse import urlsplit
            supplied = urlsplit(origin)
            expected = urlsplit(str(request.base_url))
            if supplied.scheme != expected.scheme or supplied.netloc != expected.netloc:
                return JSONResponse(status_code=403, content={"detail": "Cross-origin state changes are not allowed."})
    return await call_next(request)


@app.get("/")
def home():
    return {"message": "Welcome to SmartReceipt AI", "status": "API is running", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/auth/register", status_code=201)
def register(payload: dict, response: Response):
    name = str(payload.get("name") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    if len(name) < 2 or len(name) > 80:
        raise HTTPException(status_code=400, detail="Name must be 2 to 80 characters.")
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if len(password) < 10 or len(password) > 128:
        raise HTTPException(status_code=400, detail="Password must be 10 to 128 characters.")
    try:
        user = create_user(name, email, password, DATABASE_PATH)
    except Exception as error:
        if "UNIQUE constraint failed" in str(error):
            raise HTTPException(status_code=409, detail="An account with this email already exists.") from error
        logger.exception("Account creation failed")
        raise HTTPException(status_code=500, detail="Could not create account.") from error
    token = create_session(user["id"], DATABASE_PATH)
    response.set_cookie("sr_session", token, **_session_cookie_options())
    return {"user": user}


@app.post("/auth/login")
def login(payload: dict, request: Request, response: Response):
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    key = _auth_attempt_key(request, email)
    if auth_is_blocked(key, DATABASE_PATH):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
    user = find_user_by_email(email, DATABASE_PATH)
    if not user or not verify_password(password, user["password_hash"]):
        record_auth_failure(key, DATABASE_PATH)
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    clear_auth_failures(key, DATABASE_PATH)
    token = create_session(user["id"], DATABASE_PATH)
    response.set_cookie("sr_session", token, **_session_cookie_options())
    return {"user": {"id": user["id"], "name": user["name"], "email": user["email"]}}


@app.post("/auth/logout")
def logout(request: Request, response: Response):
    revoke_session(request.cookies.get("sr_session"), DATABASE_PATH)
    response.delete_cookie("sr_session", path="/", httponly=True,
        secure=_session_cookie_options()["secure"], samesite="strict")
    return {"ok": True}


@app.get("/auth/me")
def me(user: dict = Depends(get_current_user)):
    return {"user": user}



@app.get("/auth/sessions")
def active_sessions(user: dict = Depends(get_current_user)):
    return {"sessions": list_sessions(user["id"], DATABASE_PATH)}


@app.post("/auth/logout-all")
def logout_all(response: Response, user: dict = Depends(get_current_user)):
    revoked = revoke_all_sessions(user["id"], DATABASE_PATH)
    response.delete_cookie("sr_session", path="/", httponly=True,
        secure=_session_cookie_options()["secure"], samesite="strict")
    return {"ok": True, "revoked_sessions": revoked}


@app.post("/upload-receipt", status_code=201)
async def upload_receipt(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Authenticate, validate, store, OCR, parse, and persist one private receipt."""
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=400, detail="Only JPG, JPEG and PNG files are allowed.")

    receipt_id = str(uuid.uuid4())
    upload_path = UPLOAD_DIR / f"{receipt_id}{extension}"
    processed_path = OCR_READY_DIR / f"{receipt_id}.png"
    try:
        size = 0
        with upload_path.open("xb") as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Receipt image must be 10 MB or smaller.")
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
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid image.") from error

        if image_format not in ALLOWED_FORMATS or extension not in ALLOWED_FORMATS[image_format]:
            raise HTTPException(status_code=400, detail="The file extension and image content must match JPEG or PNG.")

        original_image = load_image(upload_path)
        processed_image = preprocess_receipt(original_image, PreprocessConfig())
        save_image(processed_path, processed_image)
        ocr_text = extract_text(processed_path)
        if not ocr_text.strip():
            raise HTTPException(status_code=422, detail="No readable text was detected in this receipt.")

        parsed_receipt, extraction_metadata = extract_receipt_fields(ocr_text)
        validation = validate_parsed_receipt(parsed_receipt)
        confidence_items = extract_text_with_confidence(processed_path)
        average_confidence = (
            round(sum(item["confidence"] for item in confidence_items) / len(confidence_items), 2)
            if confidence_items else None
        )
        review_required = (
            validation["overall_status"] != "valid"
            or average_confidence is None
            or average_confidence < 85
            or extraction_metadata.get("requires_human_review", False)
        )
        response_status = "review_required" if review_required else "success"
        ocr_summary = {
            "average_confidence": average_confidence,
            "word_count": len(confidence_items),
            "review_required": review_required,
            "extractor": extraction_metadata,
        }
        save_receipt(
            receipt_id=receipt_id, user_id=user["id"],
            original_filename=upload_path.name, processed_filename=processed_path.name,
            status=response_status, ocr_text=ocr_text, receipt=parsed_receipt,
            validation=validation, ocr=ocr_summary, database_path=DATABASE_PATH,
        )
        return {
            "message": "Receipt processed successfully.",
            "status": response_status,
            "receipt_id": receipt_id,
            "ocr_text": ocr_text,
            "receipt": parsed_receipt,
            "validation": validation,
            "ocr": ocr_summary,
        }
    except HTTPException:
        upload_path.unlink(missing_ok=True)
        processed_path.unlink(missing_ok=True)
        raise
    except (RuntimeError, FileNotFoundError) as error:
        upload_path.unlink(missing_ok=True)
        processed_path.unlink(missing_ok=True)
        logger.warning("Receipt processing dependency unavailable: %s", type(error).__name__)
        raise HTTPException(status_code=503, detail="Receipt processing is temporarily unavailable.") from error
    except Exception as error:
        upload_path.unlink(missing_ok=True)
        processed_path.unlink(missing_ok=True)
        logger.exception("Unexpected receipt processing failure")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while processing the receipt.") from error
    finally:
        await file.close()


@app.get("/receipts")
def receipt_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    q: str | None = Query(None, max_length=100),
    user: dict = Depends(get_current_user),
):
    return list_receipts(user["id"], page=page, page_size=page_size, query=q, database_path=DATABASE_PATH)



@app.get("/receipts/export.csv")
def export_receipt_history(user: dict = Depends(get_current_user)):
    records = list_reconciliation_receipts(user["id"], limit=500, database_path=DATABASE_PATH)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["receipt_id", "merchant", "date", "subtotal", "tax", "total",
                     "currency", "payment_method", "status", "created_at"])
    for item in records:
        receipt = item.get("receipt") or {}
        values = [
            item["receipt_id"], receipt.get("merchant"), receipt.get("date"),
            receipt.get("subtotal"), receipt.get("tax"), receipt.get("total"),
            receipt.get("currency"), receipt.get("payment_method"),
            item["status"], item["created_at"],
        ]
        safe = []
        for value in values:
            cell = "" if value is None else str(value)
            if cell.lstrip().startswith(("=", "+", "-", "@")):
                cell = "'" + cell
            safe.append(cell)
        writer.writerow(safe)
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="smartreceipt-history.csv"'},
    )


@app.post("/reconciliation/suggest")
def reconciliation_suggestions(payload: dict, user: dict = Depends(get_current_user)):
    lines = payload.get("lines")
    if not isinstance(lines, list) or not 1 <= len(lines) <= 200:
        raise HTTPException(status_code=400, detail="Provide between 1 and 200 statement lines.")
    for line in lines:
        if not isinstance(line, dict) or not line.get("amount") or not line.get("date"):
            raise HTTPException(status_code=400, detail="Each statement line needs amount and date.")
    receipts = list_reconciliation_receipts(user["id"], limit=500, database_path=DATABASE_PATH)
    return {
        "suggestions": suggest_matches(lines, receipts),
        "notice": "Suggestions are evidence-ranked only. No receipt is automatically matched or approved.",
    }

@app.get("/receipts/{receipt_id}")
def receipt_detail(receipt_id: str, user: dict = Depends(get_current_user)):
    receipt = get_receipt(receipt_id, user["id"], DATABASE_PATH)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    return receipt


@app.get("/receipts/{receipt_id}/image")
def receipt_image(
    receipt_id: str,
    kind: str = Query("original", pattern="^(original|processed)$"),
    user: dict = Depends(get_current_user),
):
    receipt = get_receipt(receipt_id, user["id"], DATABASE_PATH)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    filename = receipt["original_filename"] if kind == "original" else receipt["processed_filename"]
    directory = UPLOAD_DIR if kind == "original" else OCR_READY_DIR
    target = _safe_stored_path(directory, filename)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Receipt image not found.")
    return FileResponse(target, media_type="image/jpeg" if target.suffix.lower() in {".jpg", ".jpeg"} else "image/png", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@app.patch("/receipts/{receipt_id}/review")
def update_receipt_review(receipt_id: str, payload: dict = Body(...), user: dict = Depends(get_current_user)):
    status = str(payload.get("status") or "")
    fields = payload.get("fields") or {}
    if not isinstance(fields, dict) or set(fields) - REVIEW_FIELDS:
        raise HTTPException(status_code=400, detail="Review contains unsupported receipt fields.")
    clean_fields = {}
    for key, value in fields.items():
        if value is not None and not isinstance(value, (str, int, float)):
            raise HTTPException(status_code=400, detail=f"Invalid value for {key}.")
        text = "" if value is None else str(value).strip()
        if len(text) > 200:
            raise HTTPException(status_code=400, detail=f"{key} is too long.")
        clean_fields[key] = text
    if status == "approved":
        existing = get_receipt(receipt_id, user["id"], DATABASE_PATH)
        if not existing:
            raise HTTPException(status_code=404, detail="Receipt not found.")
        proposed_total = clean_fields.get("total", (existing.get("receipt") or {}).get("total"))
        normalized_total = normalize_receipt_amount(str(proposed_total or ""))
        if normalized_total is None:
            raise HTTPException(status_code=422, detail="A valid verified total is required before approval.")
        clean_fields["total"] = normalized_total
    try:
        result = review_receipt(receipt_id, user["id"], status=status, fields=clean_fields, database_path=DATABASE_PATH)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if not result:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    return result



@app.get("/receipts/{receipt_id}/review-history")
def receipt_review_history(receipt_id: str, user: dict = Depends(get_current_user)):
    events = list_review_events(receipt_id, user["id"], database_path=DATABASE_PATH)
    if events is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    return {"events": events}


@app.delete("/receipts/{receipt_id}")
def remove_receipt(receipt_id: str, user: dict = Depends(get_current_user)):
    stored = delete_receipt(receipt_id, user["id"], DATABASE_PATH)
    if not stored:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    for directory, filename in ((UPLOAD_DIR, stored["original_filename"]), (OCR_READY_DIR, stored["processed_filename"])):
        target = _safe_stored_path(directory, filename)
        target.unlink(missing_ok=True)
    return {"ok": True, "receipt_id": receipt_id}


app.mount("/app", StaticFiles(directory=PROJECT_ROOT / "frontend", html=True), name="frontend")
