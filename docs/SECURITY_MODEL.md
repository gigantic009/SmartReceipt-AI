# SmartReceipt AI security and privacy model

## Assets

- Receipt images, OCR text, parsed financial values, and reviewer corrections
- Account credentials and session tokens
- Receipt ownership and review history
- Local database, upload directory, and processed-image directory

## Trust boundaries and controls

| Boundary | Threat | Control in this branch |
|---|---|---|
| Browser to API | Cross-origin state mutation | Same-origin Origin check when supplied; SameSite=Strict session cookie |
| Authentication | Password disclosure or session replay | Salted scrypt password hashes; opaque random tokens; only SHA-256 token digests stored; logout/revoke-all |
| Account to receipt | IDOR across receipt IDs | Ownership predicate in detail, list, image, review, audit, export, and reconciliation queries |
| Upload to image parser | Spoofed image, oversized/decompression-bomb file | Content verification, JPEG/PNG allowlist, 10 MB upload cap, dimension/pixel checks |
| OCR to structured extraction | OCR prompt injection or hallucination | OCR text is untrusted; local-only optional model; field allowlist; raw amounts preserved; model output always requires human review |
| Stored receipt to browser | Sensitive image caching or framing | Private no-store responses, nosniff, frame denial, frontend CSP |
| Reviewer to final data | Silent incorrect financial values | Explicit approve/reject, verified total required for approval, before/after review event |

## Legacy migration rule

Existing receipt rows without a user owner are migrated with user_id=NULL. They are not assigned to the first account that signs in and are not visible through user-facing receipt routes. A deliberate, authenticated administrator migration process would be required to assign them.

## Reconciliation rule

Statement-to-receipt matching is evidence-ranked using amount, date, and merchant text. It returns reasons and candidate confidence but never links, approves, or modifies a receipt automatically. The current matcher is heuristic and needs benchmark evaluation before operational reliance.

## Residual risks

- No encrypted object storage, key management, retention scheduler, or tested backup/restore process yet.
- No independent penetration test, production deployment automation, distributed rate limiting, or per-account upload quota.
- OCR extraction is not yet validated against a representative multilingual ground-truth dataset.
- Local Ollama mode is optional and sends OCR text only to a loopback service; the default remains deterministic parsing. Local model output is not trusted as authoritative.
- SQLite is suitable for development and small single-process use, not a horizontally scaled production deployment.

## GODMAN-inspired engineering principles

- Least-privilege, owner-scoped tools and data access
- Bounded inputs and allowlisted structured outputs
- Human confirmation before financial approval
- Auditability and conservative fallbacks
- No hidden network transmission of receipt images or OCR data
