# SmartReceipt AI deployment

## Local development

Follow the Windows CMD setup in README.md. Tesseract must be installed locally and its language packs must match TESSERACT_LANGUAGES.

## Docker Compose

Requirements: Docker Engine and the Docker Compose plugin.

From the repository root:

    docker compose up --build

- Frontend: http://localhost:8080
- API: http://localhost:8000
- API documentation: http://localhost:8000/docs

Stop the stack:

    docker compose down

Persistent named volumes hold uploads, OCR-ready files and the SQLite database. To remove the stored data as well, run:

    docker compose down -v

That command permanently deletes the named volumes. Export anything you need first.

## Configuration

The compose file defaults to English Tesseract OCR and disables optional local AI enrichment. The Ollama integration is intentionally not wired into the container by default. Configure it only after arranging a secure local-network connection and understanding where receipt text is processed.

## Production deployment boundary

This compose stack is for local evaluation, not a hardened public deployment. Before exposing it to the internet, implement authentication and per-user authorization, encrypted storage and transport, secure secret management, malware scanning, retention/deletion policy, backups, rate limits, audit controls, monitoring and a managed database/object store. Do not publish real financial documents in a public repository.
