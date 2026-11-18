# Full-stack and production-readiness upgrade plan

This document separates the existing OCR MVP from planned capabilities. Planned items are not shipped functionality.

## Current baseline

SmartReceipt AI currently accepts JPEG/PNG uploads, validates file content and image dimensions, preprocesses images, runs Tesseract OCR, parses receipt fields with rules, reconciles financial totals, computes OCR confidence, flags uncertain results for human review, and stores results in local SQLite.

The current MVP does not yet provide authenticated users, per-user receipt access, a review interface, or production-grade encrypted storage.

## Upgrade sequence

### P0 — Identity, authorization, and privacy

- [ ] Add user registration/login and revocable server-side sessions. Use a maintained password-hashing approach; never store plaintext passwords.
- [ ] Add a user ownership column to receipt records and migrate existing local records safely. Existing records with no owner must remain private to the local administrator and must not become visible to newly registered users.
- [ ] Require authentication for upload, history, detail, review, and delete endpoints.
- [ ] Enforce ownership in every database query, not only in route/UI checks.
- [ ] Add upload quotas, per-user rate limits, request size limits, and safe error responses.
- [ ] Add retention/deletion controls, private file storage, and a documented backup/restore process.
- [ ] Keep uploads outside the public web root; use random server-generated names and never trust client filenames as filesystem paths.
- [ ] Add security tests for IDOR, unauthenticated access, expired/revoked sessions, cross-user receipt access, oversized files, spoofed MIME types, and malicious image payloads.

Acceptance: user A cannot access any receipt metadata, OCR text, original image, or processed image belonging to user B; all protected routes reject anonymous requests.

### P1 — Receipt history and human review

- [ ] Add paginated `GET /receipts` with filters for date range, merchant, status, and total.
- [ ] Add `GET /receipts/{receipt_id}` with ownership checks.
- [ ] Add review states: `review_required`, `in_review`, `approved`, and `rejected`.
- [ ] Add reviewer-edited fields and an audit trail containing who changed what and when.
- [ ] Preserve raw OCR output separately from normalized/corrected values.
- [ ] Add explicit confirmation before an edited receipt is treated as final financial data.
- [ ] Add deletion that removes the database record and both stored image files.

Acceptance: review edits are auditable, raw OCR remains recoverable, and status transitions are validated server-side.

### P2 — Extraction quality and evaluation

- [ ] Create a versioned, synthetic/redacted evaluation dataset with ground-truth merchant, date, subtotal, tax, total, currency, and payment method.
- [ ] Measure field-level exact match, normalized numeric error, date accuracy, validation precision/recall, and review-flag precision/recall.
- [ ] Report metrics by image quality, layout, language, and receipt source; do not report a single accuracy number without dataset details.
- [ ] Add regression tests for every parser correction and representative OCR failure.
- [ ] Add multilingual OCR only after language-specific evaluation data and Tesseract language packs are available.
- [ ] Keep uncertain values blank rather than guessing; expose confidence and source evidence for each extracted field.

Acceptance: each release publishes reproducible evaluation results and does not regress critical financial fields without an explicit reviewed decision.

### P3 — Frontend and deployment

- [ ] Build a responsive web UI for upload, processing status, receipt history, receipt detail, and human review.
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
