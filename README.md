# SmartReceipt AI

An AI-powered receipt scanner that extracts structured information from receipt images using OCR, normalizes financial data, and validates transactions.

## Current MVP features

- JPEG and PNG receipt upload (maximum 10 MB, 25 million pixels, and 12,000 pixels per dimension)
- Image dimension checks to reduce decompression-bomb and oversized-image risks
- Image-content verification and preprocessing with OpenCV
- OCR using Tesseract
- Receipt field extraction across common invoice label variations (bill/invoice number, date, guest/customer, tax, total, and payment labels)
- Local SQLite persistence for OCR text, parsed receipt fields, validation results, and confidence metadata
- Preservation of raw OCR amounts alongside normalized values
- Conservative handling of missing fields: uncertain values are left blank and sent for human review
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
    database.py
    image_processor.py
    image_security.py
    main.py
    ocr_corrector.py
    ocr_engine.py
    receipt_parser.py
    validate_receipt.py
  data/          # local SQLite database; ignored by Git
  uploads/       # generated uploads; ignored by Git
  ocr_ready/     # generated processed images; ignored by Git
tests/
requirements.txt
```

## Current limitations

- Receipt extraction is still rule-based. It recognizes several common label variations, but complex tables, unusual layouts, poor image quality, and OCR mistakes can still require manual review.
- The parser does not infer missing subtotal/tax/payment values from line items. This is intentional to avoid fabricating financial data.
- The current OCR pipeline uses English Tesseract and a single page-segmentation mode; multilingual receipts and difficult layouts need further evaluation.
- Receipt records are persisted locally in `backend/data/receipts.sqlite3`; the database is ignored by Git because it may contain personal and financial information.
- There are not yet authenticated receipt-history endpoints or user-level data isolation.
- The API currently returns OCR and parsed data directly; a frontend and authentication are planned.
- Human review is required for low-confidence or financially inconsistent results.

## Privacy and security

Do not commit real receipts, personal data, API keys, local database files, or environment secrets. Generated upload, preprocessing, and database directories are excluded by `.gitignore`. The current local SQLite database is not encrypted and must not be used for sensitive production data. Before deployment, add authentication, per-user authorization, retention/deletion controls, encrypted storage, and secure backups.

## Full-stack upgrade roadmap

See [docs/FULLSTACK_UPGRADE_PLAN.md](docs/FULLSTACK_UPGRADE_PLAN.md) for the staged plan covering authentication and user isolation, paginated receipt history, an auditable human-review workflow, extraction-quality evaluation, a responsive frontend, and deployment.

**Important:** these are planned upgrades, not current MVP capabilities. The current API still has no authenticated user accounts or user-level receipt ownership. Do not expose it publicly with real receipt data until the P0 security work is implemented and tested.
