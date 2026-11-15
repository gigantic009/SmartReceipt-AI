# SmartReceipt AI — Financial Document Intelligence

SmartReceipt AI is a local-first financial document intelligence prototype. It captures receipts and invoices, extracts evidence-backed financial data, flags uncertain results, organizes expenses, and makes saved records searchable and analyzable.

The project combines ideas from publicly documented commercial products and open-source receipt projects. It does not copy proprietary code, private models, branding, or protected interface assets.

## Current implemented capabilities

### Document ingestion and extraction
- JPG/JPEG/PNG/WEBP/TIFF and PDF upload with size, image-content, page-count and dimension limits.
- Multi-page PDF text extraction (embedded text first, OCR for scanned pages) and bounded batch import.
- OpenCV preprocessing and Tesseract OCR.
- Legacy receipt parser plus a universal billing representation.
- Baseline classification for receipts, invoices, hotel folios, restaurant receipts, credit notes and debit notes.
- Heuristic country/currency evidence with ambiguity handling.
- Dynamic tax entries and conservative financial reconciliation.
- OCR confidence summary and review-required status.
- Optional local Ollama LLM enrichment, disabled by default, with OCR-source evidence gating and no hosted data transfer.
- Grounded financial question-answering endpoint and assistant UI, returning ledger evidence rather than inventing figures.
- Locale-aware date normalization; ambiguous numeric dates remain unresolved when country context is insufficient.
- Structured JSON export from the frontend.

### Document library and operations
- SQLite persistence for original OCR, parsed data, validation and normalized global data.
- Searchable, filterable and paginated document register.
- Receipt detail endpoint.
- Editable normalized review fields (merchant, date, total, currency, category, notes and status).
- Receipt deletion endpoint.
- Exact-file duplicate detection using SHA-256. This detects byte-identical files only; visually similar or altered duplicates are not detected.
- CSV export of the document register.
- Line-item candidates and payment-method hints, each explicitly flagged for review.

### Expense intelligence
- Explainable keyword-based category suggestions (Travel, Food & Dining, Groceries, Shopping, Utilities, Healthcare, Office & Software).
- Manual expense entry, vendor directory and budget records.
- Document correction audit events and currency-safe combined receipt/expense analytics.
- Category suggestions remain editable and are explicitly low-confidence; this is not a trained machine-learning classifier.
- Currency-separated spend summaries by currency, category and month. Amounts in different currencies are never added together.

### Frontend
- React/Vite responsive dashboard.
- Receipt upload and extraction overview.
- Document library table with merchant/filename search.
- Financial insights summary and CSV export.
- Global coverage list removed from the primary dashboard; locale interpretation remains a backend concern.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | / | API welcome |
| GET | /health | Health check |
| POST | /upload-receipt | Validate, OCR, parse, classify and persist one image |
| GET | /receipts | Search/filter/paginate saved documents |
| GET | /receipts/{receipt_id} | Retrieve one saved document including OCR text |
| PATCH | /receipts/{receipt_id} | Correct supported normalized review fields |
| DELETE | /receipts/{receipt_id} | Delete a saved document record |
| GET | /analytics | Currency-separated spend summaries |
| GET/POST | /expenses | List and create manual expenses |
| DELETE | /expenses/{expense_id} | Delete a manual expense |
| GET/POST | /vendors | List and create vendors |
| GET/POST | /budgets | List and create budget records |
| GET | /budgets/status | Calculate period-based budget utilization |
| GET | /receipts/{receipt_id}/events | Retrieve document correction events |
| GET | /exports/receipts.csv | Download document register as CSV |
| GET | /exports/finance.xlsx | Download multi-sheet Excel report |
| GET | /reports/summary.pdf | Download PDF financial summary |

Interactive API docs: http://127.0.0.1:8000/docs

## Architecture

- API and orchestration: FastAPI, backend/app/main.py
- Image preprocessing: OpenCV/Pillow, backend/app/image_processor.py
- OCR: Tesseract, backend/app/ocr_engine.py
- Legacy extraction: backend/app/receipt_parser.py
- Universal extraction and validation: backend/app/global_billing.py
- Category suggestions: backend/app/expense_intelligence.py
- Persistence, library, duplicate lookup and analytics: backend/app/database.py
- Typed contracts: backend/app/schemas.py
- React application: frontend/

## Run locally on Windows CMD

Backend, from repository root:

    .venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

Frontend, in a second CMD window:

    cd frontend
    npm install
    npm run dev

Open http://localhost:5173.

Run tests from repository root:

    .venv\Scripts\python.exe -m pytest -q -p no:cacheprovider

Build the frontend:

    cd frontend
    npm run build


### Optional local AI enrichment (Ollama)

The deterministic parser works without an LLM. To enable optional local model suggestions, install Ollama and download a model such as llama3.1:8b, start the local Ollama service, then set these variables in the backend CMD window before starting FastAPI:

    set SMARTRECEIPT_AI_PROVIDER=ollama
    set OLLAMA_BASE_URL=http://127.0.0.1:11434
    set OLLAMA_MODEL=llama3.1:8b

This integration only permits localhost endpoints. Model suggestions are accepted only when they can be matched to OCR-visible evidence; deterministic fields are not overwritten. If Ollama is unavailable, processing falls back to the deterministic parser. Receipt text is not sent to a hosted AI service by this implementation.

## Research-informed capability roadmap

See docs/PRODUCT_CAPABILITY_BLUEPRINT.md for the researched capability matrix, inspiration sources, implementation status and phased roadmap.

Next priorities:
1. Improve extraction correctness, field-level evidence/confidence and line-item review.
2. Add robust line-item extraction and editable review UI.
3. Add PDF/multi-page/batch ingestion and asynchronous processing.
4. Add visual duplicate detection, statement import and receipt-to-transaction matching.
5. Add supplier rules, budgets, recurring expenses and richer reports.
6. Add a grounded financial assistant that answers from tested database queries and cites source receipts.
7. Add authentication, per-user isolation, encryption, retention, backups and audit logs before public deployment.

## Important limitations and security

This is a development prototype, not a finished enterprise platform or tax-compliance product.

- OCR and parsing are heuristic and can misread fields. Review extracted data before relying on it.
- Currency and country identification are not authoritative.
- Keyword categorization is a suggestion, not a trained AI model. Local LLM enrichment is optional and disabled unless explicitly configured.
- SHA-256 duplicate detection only catches exact byte-for-byte duplicates.
- Analytics summarize only records saved in the local database.
- Review APIs update normalized fields; the full visual field editor and richer correction audit UI are still planned.
- Line-item extraction is heuristic candidate detection, not guaranteed table reconstruction.
- The financial assistant currently supports a bounded set of deterministic ledger questions; it is not a general-purpose generative chatbot.
- Category and monthly analytics are grouped by currency; no foreign-exchange conversion is performed. Quantity and unit price are not inferred unless visibly captured.
- Authentication, authorization, encrypted storage, retention/deletion controls, backups, rate limiting and production monitoring are not yet implemented.

Do not expose this prototype publicly or upload real personal/financial documents to GitHub. Keep uploads, OCR output, databases and private sample receipts out of version control. Country adapters are not legal advice or tax certification; fraud signals, when implemented, must be treated as review indicators rather than accusations.
