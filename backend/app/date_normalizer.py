"""Conservative date normalization for billing documents."""
from __future__ import annotations
import re
from datetime import date, datetime


def normalize_document_date(raw: str | None, country_code: str | None = None) -> dict:
    if not raw:
        return {"value": None, "raw_text": None, "confidence": "unknown", "ambiguous": False}
    value = raw.strip()
    formats = ("%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y")
    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt).date()
            return {"value": parsed.isoformat(), "raw_text": raw, "confidence": "high", "ambiguous": False}
        except ValueError:
            pass
    match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", value)
    if match:
        first, second, year = (int(part) for part in match.groups())
        if year < 100:
            year += 2000 if year < 70 else 1900
        if first > 12 and second <= 12:
            day, month = first, second
        elif second > 12 and first <= 12:
            month, day = first, second
        elif first <= 12 and second <= 12:
            if country_code == "US":
                month, day = first, second
            elif country_code:
                day, month = first, second
            else:
                return {"value": None, "raw_text": raw, "confidence": "ambiguous", "ambiguous": True}
        else:
            return {"value": None, "raw_text": raw, "confidence": "invalid", "ambiguous": False}
        try:
            return {"value": date(year, month, day).isoformat(), "raw_text": raw,
                    "confidence": "medium" if country_code else "low", "ambiguous": False}
        except ValueError:
            return {"value": None, "raw_text": raw, "confidence": "invalid", "ambiguous": False}
    return {"value": None, "raw_text": raw, "confidence": "unknown", "ambiguous": True}
