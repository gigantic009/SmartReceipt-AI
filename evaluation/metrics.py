"""Field-level receipt parser evaluation; reports measurements, not marketing claims."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
import re
from typing import Callable


def normalize(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def numeric_value(value):
    try:
        return Decimal(re.sub(r"[^0-9.\-+]", "", str(value).replace(",", "")))
    except (InvalidOperation, ValueError):
        return None


def evaluate_records(records: list[dict], parser: Callable[[str], dict]) -> dict:
    fields: dict[str, dict] = {}
    for record in records:
        actual = parser(record.get("ocr_text", ""))
        expected = record.get("expected", {})
        for field, expected_value in expected.items():
            metric = fields.setdefault(field, {"samples": 0, "exact_matches": 0, "absolute_error_total": 0.0, "numeric_samples": 0})
            metric["samples"] += 1
            if normalize(actual.get(field)) == normalize(expected_value):
                metric["exact_matches"] += 1
            expected_number = numeric_value(expected_value)
            actual_number = numeric_value(actual.get(field))
            if expected_number is not None and actual_number is not None:
                metric["absolute_error_total"] += float(abs(expected_number - actual_number))
                metric["numeric_samples"] += 1
    summary = {}
    for field, metric in fields.items():
        samples = metric["samples"]
        numeric_samples = metric.pop("numeric_samples")
        error_total = metric.pop("absolute_error_total")
        summary[field] = {
            "samples": samples,
            "exact_match_rate": round(metric["exact_matches"] / samples, 4) if samples else None,
            "numeric_samples": numeric_samples,
            "mean_absolute_error": round(error_total / numeric_samples, 4) if numeric_samples else None,
        }
    return {"record_count": len(records), "fields": summary}
