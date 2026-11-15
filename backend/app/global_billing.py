"""Country-aware, evidence-preserving receipt extraction foundation."""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.app.line_item_extractor import extract_line_items
from backend.app.date_normalizer import normalize_document_date

CURRENCY_MARKERS = {
    "INR": ("₹", "INR", "RS."), "USD": ("USD", "US$", "$"),
    "EUR": ("€", "EUR"), "GBP": ("£", "GBP"), "CNY": ("CNY", "RMB", "¥"),
    "JPY": ("JPY", "円", "¥"), "AUD": ("A$", "AUD"), "CAD": ("C$", "CAD"),
    "CHF": ("CHF",), "SGD": ("S$", "SGD"), "AED": ("AED", "د.إ"),
}
COUNTRY_HINTS = [
    ("IN", (r"\bGSTIN\b", r"\bCGST\b", r"\bSGST\b", r"\bIGST\b", r"\bIndia\b")),
    ("US", (r"\bUnited States\b", r"\bUSA\b", r"\bU\.S\.A\.\b", r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b")),
    ("GB", (r"\bUnited Kingdom\b", r"\bVAT Registration\b", r"\bUK\b")),
    ("JP", (r"消費税", r"適格請求書", r"\bT\d{13}\b", r"日本")),
    ("CN", (r"发票", r"增值税", r"统一社会信用代码", r"中国")),
    ("DE", (r"\bDeutschland\b", r"\bUSt-IdNr\b")),
    ("FR", (r"\bFrance\b", r"\bTVA\b")),
    ("AU", (r"\bAustralia\b", r"\bABN\b")),
    ("AE", (r"\bUnited Arab Emirates\b", r"\bTRN\b")),
]
TAX_LABELS = [
    (r"CGST", "CGST", "gst_component"), (r"SGST", "SGST", "gst_component"),
    (r"IGST", "IGST", "gst_component"), (r"UTGST", "UTGST", "gst_component"),
    (r"VAT", "VAT", "vat"), (r"Sales\s*Tax", "Sales Tax", "sales_tax"),
    (r"Occupancy\s*Tax", "Occupancy Tax", "local_hospitality_tax"),
    (r"Tourism\s*Tax", "Tourism Tax", "tourism_tax"),
    (r"Consumption\s*Tax|消費税", "Consumption Tax", "consumption_tax"),
    (r"增值税", "Value Added Tax", "vat"), (r"Service\s*Tax", "Service Tax", "service_tax"),
    (r"Cess", "Cess", "cess"), (r"Customs?\s*Duty", "Customs Duty", "customs_duty"),
]
AMOUNT_RE = re.compile(r"(?<![A-Za-z])(?:₹|Rs\.?|INR|USD|US\$|EUR|€|GBP|£|CNY|RMB|JPY|¥|\$)?\s*([+-]?\d[\d,]*(?:\.\d{1,4})?)(?![A-Za-z])", re.I)

def _lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", x).strip() for x in text.splitlines() if x.strip()]

def _amounts(line: str) -> list[str]:
    return [m.group(1).replace(",", "") for m in AMOUNT_RE.finditer(line)]

def _money(value: str | None) -> str | None:
    if value is None: return None
    try: return format(Decimal(value.replace(",", "")), "f")
    except (InvalidOperation, ValueError): return None

def detect_country(text: str) -> dict[str, Any]:
    """Prefer explicit country and tax-registration clues over weak address patterns."""
    evidence = []
    for country, patterns in COUNTRY_HINTS:
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                evidence.append({"country": country, "matched_text": match.group(0)})
                break
    counts: dict[str, int] = {}
    for item in evidence:
        counts[item["country"]] = counts.get(item["country"], 0) + 1
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    if not ranked:
        return {"country_code": None, "confidence": "unknown", "evidence": []}
    winner, count = ranked[0]
    tied = len(ranked) > 1 and ranked[1][1] == count
    # Explicit country names and country-specific tax identifiers are stronger
    # than generic address fragments. Keep conflicts unresolved.
    explicit = bool(re.search(r"\bIndia\b|\bUnited States\b|\bUSA\b|\bUnited Kingdom\b|\bAustralia\b|\bUnited Arab Emirates\b", text, re.I))
    tax_clue = bool(re.search(r"\bGSTIN\b|\bCGST\b|\bSGST\b|\bIGST\b", text, re.I))
    confidence = "ambiguous" if tied else "high" if explicit or (winner == "IN" and tax_clue) or count >= 2 else "medium"
    return {"country_code": None if tied else winner, "confidence": confidence, "evidence": evidence}


def detect_currency(text: str, country_code: str | None) -> dict[str, Any]:
    """Resolve currency conservatively; OCR-noisy symbols must not override locale."""
    upper = text.upper()
    explicit_patterns = {
        "INR": r"\bINR\b|₹|\bRS\.?(?=\s*\d)",
        "USD": r"\bUSD\b|US\$",
        "EUR": r"\bEUR\b",
        "GBP": r"\bGBP\b",
        "CNY": r"\bCNY\b|\bRMB\b",
        "JPY": r"\bJPY\b",
        "AUD": r"\bAUD\b|A\$",
        "CAD": r"\bCAD\b|C\$",
        "CHF": r"\bCHF\b",
        "SGD": r"\bSGD\b|S\$",
        "AED": r"\bAED\b",
    }
    explicit = [code for code, pattern in explicit_patterns.items() if re.search(pattern, upper, re.I)]
    if len(explicit) == 1:
        return {"currency_code": explicit[0], "confidence": "high", "evidence": [f"explicit:{explicit[0]}"]}
    if len(explicit) > 1:
        return {"currency_code": None, "confidence": "ambiguous", "evidence": explicit}

    defaults = {"IN":"INR","US":"USD","GB":"GBP","JP":"JPY","CN":"CNY","DE":"EUR","FR":"EUR","AU":"AUD","AE":"AED"}
    if country_code in defaults:
        return {"currency_code": defaults[country_code], "confidence": "medium", "evidence": [f"country:{country_code}"]}

    # A bare dollar sign is shared by several currencies; yen/yuan share ¥.
    if "¥" in text:
        return {"currency_code": None, "confidence": "ambiguous", "evidence": ["symbol:¥ (CNY or JPY)"]}
    if "$" in text:
        return {"currency_code": None, "confidence": "ambiguous", "evidence": ["symbol:$ (multiple currencies)"]}
    if "€" in text:
        return {"currency_code": "EUR", "confidence": "medium", "evidence": ["symbol:€"]}
    if "£" in text:
        return {"currency_code": "GBP", "confidence": "medium", "evidence": ["symbol:£"]}
    return {"currency_code": None, "confidence": "unknown", "evidence": []}

def _labeled_amount(lines: list[str], labels: tuple[str, ...]) -> dict[str, Any] | None:
    pattern = re.compile(r"(?<![A-Za-z])(?:" + "|".join(labels) + r")(?![A-Za-z])", re.I)
    for line in lines:
        match = pattern.search(line)
        if match:
            # Use the first amount after the label. A line may contain another
            # labeled amount later (e.g. Amount Paid ... Total Amount ...).
            values = _amounts(line[match.end():])
            if values: return {"value": _money(values[0]), "raw_text": line, "confidence": "candidate"}
    return None

def _taxes(lines: list[str]) -> list[dict[str, Any]]:
    results = []
    for line in lines:
        for pattern, name, category in TAX_LABELS:
            match = re.search(pattern, line, re.I)
            if not match: continue
            values = _amounts(line[match.end():])
            if values:
                rate = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
                results.append({"name": name, "category": category,
                    "rate_percent": rate.group(1) if rate else None, "taxable_base": None,
                    "amount": _money(values[-1]), "jurisdiction": None,
                    "raw_text": line, "confidence": "candidate"})
            break
    return results

def _document_type(text: str) -> str:
    for kind, pattern in [
        ("credit_note", r"\bcredit\s*note\b"), ("debit_note", r"\bdebit\s*note\b"),
        ("hotel_folio", r"\bhotel\b|\broom\s*(?:no|number)\b|\bcheck.?out\b"),
        ("restaurant_receipt", r"\brestaurant\b|\btable\s*(?:no|number)\b|\bgratuity\b|\btip\b"),
        ("invoice", r"\binvoice\b|\bfapiao\b|发票|請求書"),
        ("receipt", r"\breceipt\b|\bthank\s*you\b")]:
        if re.search(pattern, text, re.I): return kind
    return "unknown"


def _payments(lines: list[str]) -> list[dict[str, Any]]:
    methods = []
    patterns = (("cash", r"\bcash\b"), ("card", r"\b(?:credit|debit)\s*card\b|\bvisa\b|\bmastercard\b"), ("bank_transfer", r"\b(?:bank\s*transfer|wire\s*transfer|NEFT|RTGS|IMPS)\b"), ("upi", r"\bUPI\b|@(?:ok|ybl|paytm)"), ("wallet", r"\bwallet\b|\bPayPal\b"))
    for line in lines:
        for method, pattern in patterns:
            if re.search(pattern, line, re.I):
                methods.append({"method": method, "raw_text": line, "confidence": "candidate"})
                break
    return methods

def parse_global_document(text: str) -> dict[str, Any]:
    """Extract visible evidence into a universal shape; never invent absent values."""
    lines = _lines(text)
    country = detect_country(text)
    taxes = _taxes(lines)
    subtotal = _labeled_amount(lines, (r"Sub\s*Total", r"Net\s*Amount", r"Taxable\s*Value"))
    total = _labeled_amount(lines, (r"Grand\s*Total", r"Total\s*Due", r"Invoice\s*Total", r"Total\s*Amount", r"Total"))
    discount = _labeled_amount(lines, (r"Discount", r"Less"))
    charges = _labeled_amount(lines, (r"Service\s*Charge", r"Delivery\s*Charge", r"Shipping"))
    paid = _labeled_amount(lines, (r"Amount\s*Paid", r"Paid\s*Amount", r"Payment\s*Received"))
    balance = _labeled_amount(lines, (r"Balance\s*Due", r"Outstanding", r"Due\s*Amount"))
    number = re.search(r"\b(?:Invoice|Receipt|Bill)\s*(?:No\.?|Number|#)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]{2,})", text, re.I)
    date = re.search(r"\b(?:Date|Invoice Date|Issue Date)\s*[:#-]?\s*([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})", text, re.I)
    issue_date = normalize_document_date(date.group(1) if date else None, country["country_code"])
    merchant = next((line for line in lines[:8] if len(line) >= 4 and not re.search(r"invoice|receipt|tax invoice|bill to|ship to", line, re.I)), None)
    tax_total = None
    try:
        if taxes: tax_total = format(sum(Decimal(t["amount"]) for t in taxes if t["amount"] is not None), "f")
    except InvalidOperation: pass
    return {
        "schema_version": "1.0", "document_type": _document_type(text),
        "document_number": number.group(1) if number else None,
        "issue_date_raw": date.group(1) if date else None,
        "issue_date": issue_date,
        "merchant_name_candidate": merchant,
        "country": country, "currency": detect_currency(text, country["country_code"]),
        "amounts": {"subtotal": subtotal, "discount": discount, "charges": charges,
                    "tax_total": tax_total, "grand_total": total, "amount_paid": paid, "balance_due": balance},
        "taxes": taxes, "line_items": extract_line_items(text), "payments": _payments(lines), "source_text": text,
        "extraction_warnings": [
            "Line-item rows are heuristic candidates; verify each description and amount.",
            *(["Ambiguous date formats are left unnormalized when locale evidence is insufficient."] if issue_date.get("ambiguous") else []),
            "Country and currency detection are heuristic; review medium, ambiguous or unknown results.",
            "Tax extraction is not tax-compliance verification."
        ]}

def validate_global_document(document: dict[str, Any]) -> dict[str, Any]:
    """Only reconcile fields when the required evidence exists."""
    a = document.get("amounts", {})
    checks, unresolved = [], []
    subtotal, total, tax_total = a.get("subtotal"), a.get("grand_total"), a.get("tax_total")
    if subtotal and total and (tax_total is not None or a.get("discount") or a.get("charges")):
        try:
            expected = Decimal(subtotal["value"])
            if a.get("discount") and a["discount"].get("value"): expected -= Decimal(a["discount"]["value"])
            if a.get("charges") and a["charges"].get("value"): expected += Decimal(a["charges"]["value"])
            if tax_total is not None: expected += Decimal(tax_total)
            actual = Decimal(total["value"])
            checks.append({"name":"document_total_reconciliation",
                "status":"passed" if expected == actual else "review_required",
                "expected":str(expected),"actual":str(actual),"difference":str(abs(expected-actual))})
        except (InvalidOperation, KeyError, TypeError):
            checks.append({"name":"document_total_reconciliation","status":"not_checkable"})
    else: checks.append({"name":"document_total_reconciliation","status":"not_checkable"})
    if document.get("country",{}).get("confidence") in {"unknown","ambiguous"}: unresolved.append("country")
    if document.get("currency",{}).get("confidence") in {"unknown","ambiguous"}: unresolved.append("currency")
    if not total: unresolved.append("grand_total")
    failed = any(c["status"] == "review_required" for c in checks)
    return {"status":"review_required" if failed or unresolved else "valid","checks":checks,"unresolved_fields":unresolved}
