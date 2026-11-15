"""Typed contracts for universal billing documents."""
from typing import Any, Literal
from pydantic import BaseModel, Field

class FieldEvidence(BaseModel):
    value: Any = None
    raw_text: str | None = None
    confidence: str = "unknown"
    page: int | None = None
    bbox: list[float] | None = None
    status: Literal["extracted","needs_review","not_found","not_applicable"] = "needs_review"

class TaxEntry(BaseModel):
    name: str
    category: str | None = None
    rate_percent: str | None = None
    taxable_base: str | None = None
    amount: str | None = None
    jurisdiction: str | None = None
    raw_text: str | None = None
    confidence: str = "candidate"

class UniversalBillingDocument(BaseModel):
    schema_version: str = "1.0"
    document_type: str = "unknown"
    document_number: str | None = None
    issue_date_raw: str | None = None
    merchant_name_candidate: str | None = None
    country: dict[str, Any] = Field(default_factory=dict)
    currency: dict[str, Any] = Field(default_factory=dict)
    amounts: dict[str, Any] = Field(default_factory=dict)
    taxes: list[TaxEntry] = Field(default_factory=list)
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    payments: list[dict[str, Any]] = Field(default_factory=list)
    source_text: str = ""
    extraction_warnings: list[str] = Field(default_factory=list)
