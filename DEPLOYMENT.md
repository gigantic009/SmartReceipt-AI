# Deployment and operations

SmartReceipt AI is designed for **local-first evaluation and single-user demonstration**. The included Docker Compose stack makes it easy to run consistently. It is not a hardened internet-facing service.

## 1. Local Docker deployment

Requirements: Docker Desktop/Engine and Docker Compose v2.

```bash
docker compose up --build -d
docker compose ps
```

The default port bindings listen on loopback only, so the demo is not exposed to other machines on your network.

Open:
- Frontend: http://localhost:8080
- Backend health: http://localhost:8000/health
- API documentation: http://localhost:8000/docs

Follow logs:

```bash
docker compose logs -f --tail=100
```

Stop without deleting data:

```bash
docker compose down
```

Delete containers and persistent data (irreversible):

```bash
docker compose down -v
```

## 2. Persistent data and backups

Compose creates named volumes for:
- `smartreceipt_data` — SQLite database
- `smartreceipt_uploads` — original uploaded files
- `smartreceipt_ocr` — OCR working files

Back up the database and document volume together while the application is stopped or using a consistent SQLite backup procedure. Restrict backup access because these files may contain sensitive financial information. Test restoration before relying on a backup.

## 3. Environment configuration

The default setup uses English Tesseract OCR and disables optional local AI. Copy `.env.example` to `.env` for local non-container development. Never commit real secrets or private data.

Optional Ollama enrichment is disabled by default and is not needed for the application to work. Do not expose the Ollama port publicly.

## 4. Pre-deployment checklist for a public server

Do not expose the current stack directly to the public internet. Complete and verify these items first:

- [ ] Authentication with secure session/token handling.
- [ ] Authorization and strict per-user data isolation on every API route.
- [ ] HTTPS termination, secure headers and trusted proxy configuration.
- [ ] Restrictive CORS and origin/CSRF protections suitable for the chosen auth model.
- [ ] Rate limits, request timeouts and upload quotas.
- [ ] Malware/content scanning and robust file lifecycle controls.
- [ ] Encryption at rest and encrypted, tested backups.
- [ ] Secret management outside source control and container images.
- [ ] Retention, export and deletion policies for uploaded financial records.
- [ ] Audit logging that avoids leaking sensitive OCR contents.
- [ ] Monitoring, alerting, dependency scanning and incident response.
- [ ] Production database and object-storage design with migration/restore testing.
- [ ] Load, concurrency and failure-recovery tests.

## 5. Suggested production architecture (future work)

For a multi-user deployment, place a TLS reverse proxy in front of the frontend and API; add an identity layer and per-user authorization; move from local SQLite/filesystem storage to a managed relational database and private object storage; and run OCR in isolated background workers with queue limits. Keep uploaded files private and short-lived where possible.

## 6. Verification

Before a release candidate:
1. Run the backend pytest suite.
2. Build the frontend with `npm run build`.
3. Build both Docker images.
4. Test upload, correction, deletion, exports and transaction matching with synthetic documents.
5. Restart the stack and confirm the database and files persist.
6. Restore a backup into a clean environment and verify the result.
7. Check logs for errors and ensure no private OCR text or credentials are emitted.

A successful local Docker build is a packaging check, not a production security certification.
