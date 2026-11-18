"""Evaluate the deterministic receipt parser against a JSONL ground-truth file.

Each line must be {"ocr_text": "...", "expected": {"field": "value"}}.
Use only synthetic or redacted receipts; do not commit real customer receipts.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from backend.app.receipt_parser import parse_receipt
from evaluation.metrics import evaluate_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure field-level SmartReceipt parser quality.")
    parser.add_argument("dataset", type=Path, help="UTF-8 JSONL dataset")
    args = parser.parse_args()
    records = []
    with args.dataset.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict) or not isinstance(record.get("ocr_text"), str) or not isinstance(record.get("expected"), dict):
                raise ValueError(f"Invalid evaluation record on line {line_number}.")
            records.append(record)
    print(json.dumps(evaluate_records(records, parse_receipt), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
