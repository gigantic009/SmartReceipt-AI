

from fastapi import FastAPI, UploadFile, File, HTTPException
from pathlib import Path
import shutil
import uuid

app = FastAPI(
    title="SmartReceipt AI",
    description="AI-powered receipt scanning and expense management API",
    version="0.2.0"
)

# Folder for uploaded receipts
UPLOAD_DIR = Path("backend/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed image formats
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


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

    # Check file extension
    extension = Path(file.filename or "").suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, JPEG and PNG files are allowed."
        )

    # Generate a unique filename
    unique_filename = f"{uuid.uuid4()}{extension}"
    file_path = UPLOAD_DIR / unique_filename

    try:
        # Save uploaded image
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {
            "message": "Receipt uploaded successfully!",
            "filename": unique_filename,
            "status": "success"
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Could not save the uploaded receipt."
        )

    finally:
        await file.close()
