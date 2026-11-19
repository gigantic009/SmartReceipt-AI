# Full-stack and production-readiness upgrade plan

This document separates the existing OCR MVP from planned capabilities. Planned items are not shipped functionality.

## Current baseline

SmartReceipt AI currently accepts JPEG/PNG uploads, validates file content and image dimensions, preprocesses images, runs Tesseract OCR, parses receipt fields with rules, reconciles financial totals, computes OCR confidence, flags uncertain results for human review, and stores results in local SQLite.

The current MVP does not yet provide authenticated users, per-user receipt access, a review interface, or production-grade encrypted storage.

## Upgrade sequence

### P0 — Identity, authorization, and privacy

- [x] Add user registration/login and revocable server-side sessions. Passwords use salted scrypt hashes; only SHA-256 digests of opaque session tokens are stored.
- [x] Add a user ownership column to receipt records and migrate existing local records safely. Existing unowned records remain unassigned and invisible to user accounts.
- [x] Require authentication for upload, history, detail, image, review, export, reconciliation suggestions, and delete endpoints.
- [x] Enforce owner IDs in receipt reads, writes, image delivery, review events, export, and reconciliation candidate queries.
- [ ] Add upload quotas and per-user rate limits; current upload size limits and login throttling are implemented, but quotas and distributed rate limiting remain.
- [ ] Add retention policies, encrypted private object storage, and a tested backup/restore process. Account-scoped deletion is implemented.
- [ ] Keep uploads outside the public web root; use random server-generated names and never trust client filenames as filesystem paths.
- [x] Add security tests for unauthenticated access, account isolation/IDOR, hashed sessions, and legacy migration. Upload abuse and revoked/expired session tests still need expansion.

Acceptance: user A cannot access any receipt metadata, OCR text, original image, or processed image belonging to user B; all protected routes reject anonymous requests.

### P1 — Receipt history and human review

- [x] Add paginated `GET /receipts` with text search; structured date/merchant/status/total filters remain.
- [x] Add `GET /receipts/{receipt_id}` with ownership checks.
- [x] Add reviewer decisions `approved` and `rejected` with `review_required` as the extraction state. An explicit `in_review` assignment state remains.
- [x] Add reviewer-edited fields and an audit trail containing account, prior/new status, and before/after values.
- [ ] Preserve raw OCR output separately from normalized/corrected values.
- [ ] Add explicit confirmation before an edited receipt is treated as final financial data.
- [x] Add account-scoped deletion for the record and both stored image files.

Acceptance: review edits are auditable, raw OCR remains recoverable, and status transitions are validated server-side.

### P2 — Extraction quality and evaluation

- [x] Add a field-level evaluation harness, CLI runner, and small synthetic smoke-test dataset. A representative, versioned/redacted ground-truth benchmark remains required.
- [ ] Measure field-level exact match, normalized numeric error, date accuracy, validation precision/recall, and review-flag precision/recall.
- [ ] Report metrics by image quality, layout, language, and receipt source; do not report a single accuracy number without dataset details.
- [ ] Add regression tests for every parser correction and representative OCR failure.
- [ ] Add multilingual OCR only after language-specific evaluation data and Tesseract language packs are available.
- [ ] Keep uncertain values blank rather than guessing; expose confidence and source evidence for each extracted field.

Acceptance: each release publishes reproducible evaluation results and does not regress critical financial fields without an explicit reviewed decision.

### P3 — Frontend and deployment

- [x] Build a responsive web UI for upload, processing status, receipt history, receipt detail, human review, CSV export, and statement match suggestions.
- [ ] Add accessible labels, keyboard navigation, loading/error/empty states, and mobile upload support.
- [ ] Add containerized deployment, environment-based configuration, health/readiness checks, structured logs, and monitoring.
- [ ] Use private object storage and encryption at rest for production receipt images; keep storage credentials outside source control.
- [ ] Add database migrations and tested backup/restore procedures.
- [ ] Add CI coverage for API integration, auth isolation, migration, and frontend end-to-end flows.

Acceptance: a new environment can be deployed from documented steps, health checks work, and a restore drill succeeds without exposing receipt files publicly.

## API contract proposal

- `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- `POST /upload-receipt` — authenticated upload, with owner ID taken only from the authenticated session.
- `GET /receipts` — paginated, user-scoped history.
- `GET /receipts/{receipt_id}` — user-scoped receipt details.
- `PATCH /receipts/{receipt_id}/review` — validated reviewer edits and audit record.
- `DELETE /receipts/{receipt_id}` — user-scoped record and file deletion.

Never accept an owner/user ID from the upload body as the authority for ownership. Derive it from the authenticated principal.

## Data and migration notes

- Add a `users` table and session/token storage with hashed opaque tokens and expiry/revocation.
- Add `user_id` to receipts with a foreign key and index.
- Existing unowned receipt rows must not be assigned to the first user who signs in. Keep them inaccessible through user-facing routes until an explicit local-admin migration decision is made.
- Add a `receipt_review_events` table for immutable review history.
- Store file paths as server-generated identifiers, not user-controlled paths.

## Delivery rule

Do not mark a checkbox complete until implementation, automated tests, and documentation are merged. This document is an implementation plan, not evidence that the listed endpoints or features already exist.


## Reference products and design decisions

- [Receipt Tracker](https://github.com/luizpersechini/receipt-tracker): study local-first OCR and receipt-to-statement reconciliation as a product workflow.
- [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx): study document ingestion, metadata search, retention and document lifecycle controls.
- [GODMAN](https://github.com/gigantic009/GODMAN): apply explicit allowlists, bounded inputs, fail-safe behavior, audit records, and user confirmation for consequential actions. This is an engineering pattern reference; no GODMAN code is imported.
- Matching suggestions are explainable and never auto-confirmed. The current algorithm is heuristic and must be evaluated before being trusted for financial reconciliation.
