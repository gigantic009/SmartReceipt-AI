"""Optional local LLM enrichment with strict OCR-evidence gating.

Disabled by default. When enabled, calls only a local Ollama endpoint; no receipt
text is sent to a hosted provider. Model suggestions never overwrite deterministic
fields and must be traceable to text present in the OCR source.
"""
from __future__ import annotations
import json
import os
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def _normalize_amount(value) -> str | None:
    if value is None:
        return None
    try:
        return format(Decimal(str(value).replace(",", "").strip()), "f")
    except (InvalidOperation, ValueError):
        return None


def _visible_in_source(value, source: str) -> bool:
    if value is None:
        return False
    token = str(value).strip()
    if not token:
        return False
    return token.casefold() in source.casefold()


def enrich_with_local_model(document: dict, ocr_text: str) -> dict:
    """Return document enriched only with conservative, source-grounded model hints."""
    provider = os.getenv("SMARTRECEIPT_AI_PROVIDER", "disabled").lower()
    if provider in {"", "disabled", "none", "off"}:
        document["ai_enrichment"] = {"enabled": False, "provider": "disabled"}
        return document
    if provider != "ollama":
        document.setdefault("extraction_warnings", []).append(
            "Unsupported AI provider configured; deterministic extraction was used."
        )
        document["ai_enrichment"] = {"enabled": False, "provider": provider, "status": "unsupported"}
        return document

    endpoint = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        document["ai_enrichment"] = {"enabled": False, "provider": "ollama", "status": "blocked_nonlocal_endpoint"}
        document.setdefault("extraction_warnings", []).append("Local AI endpoint must use localhost over HTTP.")
        return document

    model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    prompt = (
        "Extract candidate fields from this OCR text. Return only JSON with keys "
        "merchant_name_candidate, document_type, document_number, issue_date_raw, "
        "currency_code, amounts, taxes, line_items, payments. Each amount value must "
        "be a string exactly visible in OCR. Never calculate, infer or invent missing data. "
        "Use null or empty arrays when uncertain. Preserve exact raw_text for every candidate. "
        "OCR TEXT:\n" + ocr_text[:18000]
    )
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False, "format": "json"}).encode()
    request = Request(endpoint + "/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
        candidate = json.loads(body.get("response", "{}"))
        if not isinstance(candidate, dict):
            raise ValueError("Model response must be a JSON object.")
    except Exception:
        document["ai_enrichment"] = {"enabled": True, "provider": "ollama", "model": model, "status": "unavailable"}
        document.setdefault("extraction_warnings", []).append(
            "Local AI enrichment was unavailable; deterministic extraction remains in use."
        )
        return document

    merged = []
    for field in ("merchant_name_candidate", "document_number", "issue_date_raw"):
        value = candidate.get(field)
        if document.get(field) is None and isinstance(value, str) and _visible_in_source(value, ocr_text):
            document[field] = value
            merged.append(field)

    proposed_type = candidate.get("document_type")
    allowed_types = {"receipt", "invoice", "hotel_folio", "restaurant_receipt", "credit_note", "debit_note", "unknown"}
    if document.get("document_type") == "unknown" and proposed_type in allowed_types:
        document["document_type"] = proposed_type
        merged.append("document_type")

    proposed_currency = candidate.get("currency_code")
    if document.get("currency", {}).get("currency_code") is None and isinstance(proposed_currency, str):
        if re.search(r"\b" + re.escape(proposed_currency) + r"\b", ocr_text, re.I):
            document.setdefault("currency", {})["currency_code"] = proposed_currency.upper()
            document["currency"]["confidence"] = "model_candidate"
            document["currency"].setdefault("evidence", []).append("local_model_candidate_visible_in_ocr")
            merged.append("currency")

    for field in ("subtotal", "discount", "charges", "grand_total", "amount_paid", "balance_due"):
        current = document.get("amounts", {}).get(field)
        proposed = candidate.get("amounts", {}).get(field) if isinstance(candidate.get("amounts"), dict) else None
        if current is None and isinstance(proposed, str):
            normalized = _normalize_amount(proposed)
            if normalized and re.sub(r"[^\d]", "", normalized) in re.sub(r"[^\d]", "", ocr_text):
                document["amounts"][field] = {
                    "value": normalized, "raw_text": proposed,
                    "confidence": "model_candidate", "source": "local_model",
                }
                merged.append("amounts." + field)

    existing_tax_lines = {str(item.get("raw_text", "")).casefold() for item in document.get("taxes", [])}
    for tax in candidate.get("taxes", []) if isinstance(candidate.get("taxes"), list) else []:
        if not isinstance(tax, dict) or not _visible_in_source(tax.get("raw_text"), ocr_text):
            continue
        raw = tax["raw_text"].casefold()
        amount = _normalize_amount(tax.get("amount"))
        if not amount or raw in existing_tax_lines:
            continue
        document.setdefault("taxes", []).append({
            **tax, "amount": amount, "confidence": "model_candidate",
            "source": "local_model", "needs_review": True,
        })
        existing_tax_lines.add(raw)
        merged.append("tax_candidate")

    document["ai_enrichment"] = {
        "enabled": True, "provider": "ollama", "model": model,
        "status": "completed", "accepted_candidate_fields": merged,
        "rejected_or_unmatched_candidates": "Not applied; deterministic fields are preserved.",
    }
    return document
