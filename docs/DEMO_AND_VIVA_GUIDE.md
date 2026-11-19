# SmartReceipt AI: Demonstration and Viva Guide

## 6-minute demonstration
1. Register/sign in and explain account isolation.
2. Upload a clear synthetic receipt image; show processing and extracted fields.
3. Open the receipt and compare the fields with the original image and raw OCR evidence.
4. Correct one field and approve only after checking it.
5. Show the history search and export.
6. Enter a synthetic statement line and show explainable match suggestions; stress that they are suggestions only.
7. Briefly explain deterministic extraction and the optional local Ollama mode.

## Architecture (explain in plain language)
- Browser: a small JavaScript interface handles upload, review, search and display.
- FastAPI: routes authenticate users, validate uploads and expose receipt workflows.
- OCR: image preprocessing and Tesseract produce text; deterministic rules extract fields.
- Optional local AI: Ollama can structure OCR text, but is restricted to local endpoints and results still require human review.
- SQLite: stores users, sessions, receipt metadata, reviews and ownership; the API only returns the current user's records.
- Tests/evaluation: automated tests check route, parser and ownership behaviours. The sample evaluation is a smoke test, not a representative accuracy benchmark.

## Suggested viva questions
- Why does OCR need human review?
- Why preserve raw OCR text and the original image?
- Why is model output not treated as truth?
- What does account isolation mean?
- What does the reconciliation score represent, and why does it not auto-confirm?
- What are the limitations of the current evaluation dataset?
- Why use SQLite for a student demonstration, and what would change for a larger deployment?

## Demo setup checklist
- Use synthetic receipts with varied layouts and no real personal information.
- Have one clean receipt, one difficult/low-quality receipt and one receipt with ambiguous totals.
- Verify Tesseract is installed and accessible.
- If showing optional Ollama, download the model in advance and test local mode; otherwise demo deterministic rules.
- Run tests and verify the app before presenting.
