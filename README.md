# SmartReceipt AI

An AI-powered receipt scanner that extracts structured information from receipt images using OCR, normalizes financial data, and validates transactions.

## Current MVP features

- JPEG and PNG receipt upload (maximum 10 MB)
- Image-content verification and preprocessing with OpenCV
- OCR using Tesseract
- Receipt field extraction and amount normalization
- Tax-total and payment reconciliation
- OCR confidence summary and review-required status
- Automated unit tests for parsing, normalization, and validation

## Requirements

- Python 3.10 or newer
- Tesseract OCR with the English language data installed
- Python dependencies from `requirements.txt`

### Install Tesseract

Install Tesseract OCR for your operating system.

On Windows, the default installer location is:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

If Tesseract is installed elsewhere or is not on PATH, set `TESSERACT_CMD` to its executable path.

Windows CMD example:

```cmd
set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Linux/macOS: ensure the `tesseract` executable is available on PATH, or set `TESSERACT_CMD`.

## Setup

Run commands from the repository root.

### Windows CMD

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Start the API

```cmd
uvicorn backend.app.main:app --reload
```

Open the interactive API documentation at:

- http://127.0.0.1:8000/docs

Health check:

- http://127.0.0.1:8000/health

## Run tests

```cmd
python -m pytest -q
```

## API endpoint

### `POST /upload-receipt`

Send a multipart form request with the image in a field named `file`.

The response includes:

- Receipt identifier and stored filenames
- Raw OCR text
- Extracted and normalized receipt fields
- Financial validation results
- Average OCR confidence and review status

A receipt marked `review_required` should be checked by a person. OCR output is not guaranteed to be correct, and the application does not silently infer missing financial values.

## Project structure

```text
backend/
  app/
    image_processor.py
    main.py
    ocr_corrector.py
    ocr_engine.py
    receipt_parser.py
    validate_receipt.py
  uploads/       # generated uploads; ignored by Git
  ocr_ready/     # generated processed images; ignored by Git
tests/
requirements.txt
```

## Current limitations

- The MVP uses rule-based extraction tailored to the current sample receipt format; it is not yet a general-purpose parser for every merchant layout.
- Receipt records are not yet persisted in a database.
- The API currently returns OCR and parsed data directly; a frontend and authentication are planned.
- Human review is required for low-confidence or financially inconsistent results.

## Privacy and security

Do not commit real receipts, personal data, API keys, or environment secrets. Generated upload and preprocessing directories are excluded by `.gitignore`.
