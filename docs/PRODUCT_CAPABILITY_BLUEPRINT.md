# SmartReceipt AI — Product Capability Blueprint

## Product direction

Build an evidence-first financial document intelligence platform. The product combines document capture, extraction, review, expense organization, reconciliation, analytics and export. It is inspired by publicly documented workflows in commercial products and open-source projects; it does not copy proprietary source code, branding, models, or protected UI assets.

## Capability map

| Capability | Product inspiration / public evidence | Project status |
|---|---|---|
| Receipt, invoice and hotel-folio classification | Veryfi document types | Baseline heuristic |
| Multi-stage image preprocessing and OCR | Veryfi, open-source OCR projects | Existing Tesseract/OpenCV |
| Structured merchant, date, currency and totals | Zoho Autoscan, ReceiptIQ | Partial |
| Tax and payment extraction | Veryfi document schema | Partial |
| Line-item extraction | Veryfi, Dext | Heuristic candidates added; full table reconstruction planned |
| Field-level confidence and evidence | Veryfi, evidence-first open-source projects | Partial; OCR average only |
| Human correction and review queue | Dext, Expensify | Correction UI, API and event history baseline added |
| Persistent searchable document register | ReceiptIQ, SpendLens | API + UI baseline added |
| Exact-file duplicate detection | Veryfi, invoice-intelligence projects | SHA-256 baseline added |
| Explainable expense category suggestions | Dext, Zoho | Keyword baseline added |
| Currency-separated spend analytics | Open-source expense trackers | Baseline API + UI added |
| CSV export | Expense tracker projects | Added |
| XLSX/PDF report generation | SpendLens, Receipt Tracker | Added; currency-separated reports |
| Statement import and receipt matching | Receipt Tracker, Ramp, Expensify | CSV import and explainable matching with manual confirmation added |
| Supplier rules and auto-categorization | Dext | Planned |
| Budgets, recurring expenses and alerts | Open-source expense trackers | Budget records and utilization alerts added; recurring expenses planned |
| Email / cloud inbox ingestion | Dext, Receipt Tracker | Planned |
| Natural-language financial assistant with cited records | Receipt Intelligence | Bounded ledger Q&A and evidence payloads added; generative conversational layer planned |
| Fraud, tampering, screenshot and blur analysis | Veryfi | Planned; must be treated as review signals, not fraud verdicts |
| Authentication, workspaces, audit and retention | Enterprise document platforms | Audit baseline and local Docker stack added; authentication and hardening required before multi-user/public deployment |

## Current backend API additions

- `POST /transactions/import-csv`, `GET /transactions`, match-candidate and confirmation routes: bank statement reconciliation.
- Local Dockerfile, frontend Dockerfile, Compose stack and deployment guide added for evaluation.

- `POST /upload-document` and `POST /upload-batch`: PDF/image and bounded batch ingestion.
- `POST /assistant/query`: deterministic financial question answering over local saved records.
- `GET /exports/finance.xlsx` and `GET /reports/summary.pdf`: spreadsheet and PDF reports.
- `GET /budgets/status`: period-based budget utilization and threshold status.
- Optional local Ollama extraction enrichment is disabled by default and accepts only OCR-visible candidate fields.

- GET /receipts: searchable, filterable, paginated document register.
- GET /receipts/{receipt_id}: record details including OCR text.
- PATCH /receipts/{receipt_id}: correct supported review fields.
- DELETE /receipts/{receipt_id}: delete a saved record.
- GET /analytics: document counts, review counts, spend by currency/category/month.
- GET /exports/receipts.csv: CSV register export.
- Upload response includes exact SHA-256 duplicate match information and a category suggestion.

## Design and engineering principles

1. Evidence first: preserve OCR text and source evidence; do not invent missing values.
2. AI assists, deterministic code verifies: language models may propose structured fields, but money arithmetic and reconciliation use decimal arithmetic in code.
3. Currency safety: never add amounts across currencies without an explicit exchange-rate source, timestamp and conversion record.
4. Human control: uncertain fields remain reviewable; category and extraction suggestions are editable.
5. Privacy by default: local-first development, no receipt images or extracted personal data in Git.
6. Modular services: ingestion, OCR, extraction, validation, categorization, persistence, reconciliation, analytics and export remain separate.
7. Transparent confidence: distinguish OCR character confidence, extraction confidence and business-rule validation; do not present one as another.
8. No unsupported claims: duplicate hashes detect identical files, not visually similar or altered copies. Keyword categorization is a suggestion, not a trained AI model.

## Next implementation stages

### P0 — Extraction and review correctness
- Field-level evidence and confidence.
- Robust merchant/date/document-number extraction.
- Line-item extraction with row-level tax and totals.
- Review editor with correction history.
- Currency-safe amount-paid / total / balance semantics.

### P1 — Document operations
- Improve statement CSV column mapping and support additional bank export formats.
- Add transaction unmatch/edit and reconciliation audit UI.
- PDF and multi-page support.
- Batch upload and asynchronous processing jobs.
- Visual duplicate detection and cross-document duplicate review.
- Full-text search and document filters.
- XLSX and PDF report exports.
- Locale-aware date normalization and grounded ledger question answering.

### P2 — Expense management
- Manual expenses and refunds.
- Supplier/vendor directory and configurable rules.
- Categories, projects, tags, budgets and recurring expenses.
- Statement import and explainable receipt-to-transaction matching.

### P3 — Intelligence and automation
- Local/optional LLM structured extraction with schema validation and deterministic fallback.
- Natural-language questions answered from tested database queries with receipt citations.
- Anomaly signals and document quality checks.
- Email ingestion and accounting integrations.

### P4 — Production readiness
- Authentication, authorization and workspace isolation.
- Encrypted file storage, backups, deletion/retention controls.
- Audit logs, rate limits, malware/file scanning and secrets management.
- Observability, migrations, deployment and disaster recovery.

## Security and compliance boundary

The current project is a local prototype. It is not yet safe for public deployment with real financial or identity documents. Do not upload real customer receipts to a public repository. Tax-country hints are not tax-law certification. Fraud signals are not determinations of wrongdoing.
