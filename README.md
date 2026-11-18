# SmartReceipt AI

A private receipt-processing workspace built with FastAPI, OpenCV, Tesseract OCR, SQLite, and a responsive web interface. It extracts receipt data, validates financial totals, and keeps human corrections auditable.

> **Status:** Active portfolio project. Authentication, user-scoped receipt storage, review, history, and a browser UI are implemented in this upgrade branch. OCR extraction remains rule-based and requires evaluation against a representative dataset before accuracy claims or production use.

## Product capabilities

### Capture and extraction
- JPEG/PNG upload with a 10 MB limit and image dimension/decompression-bomb checks
- Content-based format verification, OpenCV preprocessing, and Tesseract OCR
- Receipt field parsing, amount normalization, tax/total validation, and confidence summary
- Uncertain or inconsistent results are flagged for human review; missing values are not silently invented

### Accounts and privacy
- Registration and login with salted scrypt password hashes
- Random opaque session tokens; only SHA-256 token digests are stored
- HttpOnly, SameSite=Strict session cookies; set `COOKIE_SECURE=true` in production behind HTTPS
- Failed-login throttling by IP/email key
- Every receipt query is scoped to the authenticated account
- Legacy receipt rows are migrated with a null owner and are never assigned to a newly registered user
- Original and processed images are stored outside the static frontend and served only after an ownership check

### History and human review
- Paginated receipt history and OCR/parsed-text search
- Receipt detail and authenticated original/processed image retrieval
- Reviewer edits for merchant, date, subtotal, tax, total, currency, and payment method
- Approve/reject decisions with before/after review events in an audit table
- Delete removes the owned record and its associated image files

### Web application
- Responsive sign-in/register flow, upload workspace, history search, detail view, image preview, and review form
- Keyboard-accessible native forms and explicit approve/reject actions
- Open the UI at `/app/`; API documentation is at `/docs`

## Technology

| Layer | Technology |
|---|---|
| API | FastAPI, Python 3.10+ |
| Image processing | OpenCV, Pillow |
| OCR | Tesseract via pytesseract |
| Persistence | SQLite with explicit ownership and migrations |
| Authentication | Python scrypt, opaque random sessions, SHA-256 token digests |
| Frontend | HTML, CSS, vanilla JavaScript |
| Tests | pytest, FastAPI TestClient / HTTPX |

## Setup

### Requirements
- Python 3.10 or newer
- Tesseract OCR with English language data installed
- Dependencies from `requirements.txt`

On Windows, the default Tesseract path is:
```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```
If needed, set `TESSERACT_CMD` to the executable path.

### Install and run (Windows CMD)
```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Open:
- Web app: http://127.0.0.1:8000/app/
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

For production, terminate TLS at a trusted reverse proxy and set:
```text
COOKIE_SECURE=true
ENVIRONMENT=production
```
You can override local data paths with `SMARTRECEIPT_DB_PATH`, `SMARTRECEIPT_UPLOAD_DIR`, and `SMARTRECEIPT_OCR_READY_DIR`. Keep all three outside the public static directory and back them up securely.

## API

All receipt endpoints and `/auth/me` require a valid session.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Sign in |
| POST | `/auth/logout` | Revoke current session |
| GET | `/auth/me` | Current account |
| POST | `/upload-receipt` | Upload, OCR, validate, and save a private receipt |
| GET | `/receipts` | Paginated owned history; supports `page`, `page_size`, `q` |
| GET | `/receipts/{id}` | Owned receipt detail |
| GET | `/receipts/{id}/image?kind=original` | Owned original/processed image |
| PATCH | `/receipts/{id}/review` | Edit allowed fields and approve/reject with audit event |
| DELETE | `/receipts/{id}` | Delete owned record and images |

Review request example:
```json
{
  "status": "approved",
  "fields": {
    "merchant": "Example Store",
    "total": "125.50",
    "currency": "INR"
  }
}
```

## Run tests

```cmd
python -m pytest -q
```

Tests cover parser/validation behavior, image security, database persistence, scrypt password verification, hashed session storage, account isolation, legacy receipt migration, authenticated API behavior, review auditing, and static frontend serving.

## Project structure

```text
backend/app/
  auth.py                 # password hashing and opaque session tokens
  database.py             # migrations, account ownership, receipt history and audit
  image_processor.py
  image_security.py
  main.py                 # authenticated FastAPI routes
  ocr_corrector.py
  ocr_engine.py
  receipt_parser.py
  validate_receipt.py
frontend/
  index.html
  app.js
  styles.css
tests/
```

## Security and privacy boundaries

- Do not commit real receipts, personal data, API keys, SQLite databases, or environment secrets.
- Legacy unowned receipt records remain inaccessible to user accounts; there is no automatic owner assignment.
- Session cookies are HttpOnly and SameSite=Strict. Production must use HTTPS and `COOKIE_SECURE=true`.
- Stored images are not exposed by static hosting; image routes perform receipt ownership checks.
- Review events preserve who changed a receipt, the prior/new status, and before/after field values.
- The OCR engine is not a guarantee of correctness. A human must verify amounts against the source image. The reconciliation endpoint ranks candidate receipts by amount, date, and merchant text, explains the evidence, and never confirms a match automatically.
- SQLite files and uploaded images need encrypted storage, tested backups, retention policy, and operational monitoring before handling real customer financial data.

## Roadmap

See [docs/FULLSTACK_UPGRADE_PLAN.md](docs/FULLSTACK_UPGRADE_PLAN.md). Remaining major work includes a reproducible OCR evaluation benchmark, multi-layout and multilingual extraction, statement-to-receipt reconciliation, encrypted object storage, retention controls, deployment automation, and production observability.

## Research references

The product workflow was informed by open-source patterns from [Actual Budget](https://github.com/actualbudget/actual) and [Firefly III](https://github.com/firefly-iii/firefly-iii) for financial data integrity and auditability, and [Receipt Tracker](https://github.com/luizpersechini/receipt-tracker) for local-first OCR and receipt/statement reconciliation concepts. SmartReceipt AI is an independent implementation; no third-party source code is copied.
