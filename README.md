# SmartReceipt AI — Global Billing Intelligence

SmartReceipt AI is evolving from a fixed-format receipt parser into a country-aware document extraction platform. It aims to read receipts, invoices, hotel folios, restaurant bills, credit notes and other billing documents, then normalize evidence-backed information into a common representation.

## Current development foundation

- Existing FastAPI, OpenCV, Tesseract and SQLite processing pipeline retained.
- Universal global document interpretation is added alongside the legacy parser.
- Dynamic tax entries preserve original labels rather than requiring CGST/SGST.
- Country and currency detection return confidence and evidence.
- Financial reconciliation runs only when the required extracted values exist.
- React/Vite frontend provides upload, extraction overview, tax breakdown, warnings and JSON export.
- Regression tests cover Indian GST, a US hotel occupancy-tax invoice, Japanese billing clues and ambiguous currency symbols.

This is a foundation, not complete worldwide coverage or tax-law certification. Country detection is heuristic. Reliable line-item extraction, multilingual OCR, jurisdictional rule packs, date normalization, official registration verification and review editing remain future work.

## Architecture

- OCR: existing FastAPI/Tesseract/OpenCV pipeline.
- Universal interpretation: backend/app/global_billing.py.
- Locale hints: backend/app/locale_registry.py.
- Typed contracts: backend/app/schemas.py.
- Frontend: React + Vite in frontend/.
- Persistence: existing local SQLite storage.

The original OCR coordinate experiments remain sample-specific and separate from global parsing.

## Requirements

- Python 3.10+
- Tesseract OCR and appropriate language packs
- Node.js 20+ and npm
- Python packages from requirements.txt

## Start backend (Windows CMD)

From the repository root:

\`\`\`cmd
python -m venv .venv
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
uvicorn backend.app.main:app --reload
\`\`\`

API documentation: http://127.0.0.1:8000/docs

## Start frontend (Windows CMD)

Open a second CMD window:

\`\`\`cmd
cd /d path\\to\\SmartReceipt-AI\\frontend
npm install
npm run dev
\`\`\`

Open http://localhost:5173. By default, the frontend calls http://127.0.0.1:8000. Set VITE_API_URL in frontend/.env to override the API URL.

## Run tests

\`\`\`cmd
python -m pytest -q
\`\`\`

## Universal document contract

The global extraction object includes document type and identifier, country and currency decisions with confidence/evidence, dynamic taxes[], optional monetary fields, line-item and payment collections, source OCR text and extraction warnings. Missing fields are not fabricated. A currency symbol such as $ or ¥ may be ambiguous and should be reviewed when evidence is insufficient.

## Safety and production readiness

The current API stores uploaded documents and OCR text locally. Authentication, per-user authorization, encrypted storage, retention/deletion controls and production-grade secret management are not yet implemented. Do not expose this prototype publicly with real personal or financial documents until these controls are implemented.

Country adapters are interpretation aids, not legal advice or tax-compliance certification. Tax rules must be versioned, sourced from official authorities, reviewed by qualified specialists and tested by jurisdiction before being used for compliance decisions.
