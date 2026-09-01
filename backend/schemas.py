"""Pydantic request/response schemas for public API contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PredictionRequest(BaseModel):
    amount_inr: float = Field(gt=0, le=10_000_000)
    decline_reason: str = Field(min_length=1)
    payment_method: Literal["UPI", "Credit Card", "Debit Card", "Net Banking"]
    hour_of_day: int = Field(ge=0, le=23)
    day_of_month: int = Field(ge=1, le=31)
    day_of_week: int = Field(ge=0, le=6)
    customer_previous_success_rate: float = Field(ge=0, le=1)
    customer_previous_failure_count: int = Field(ge=0, le=10_000)
    days_since_last_successful_payment: float = Field(ge=-1, le=10_000)

    @field_validator("decline_reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip().lower()


class SimulationRequest(PredictionRequest):
    transaction_id: str | None = Field(default=None, min_length=1, max_length=100)


class CandidateScore(BaseModel):
    candidate_retry_hours: float
    calibrated_probability: float
    confidence_tier: Literal["Low", "Medium", "High"]


class PredictionResponse(BaseModel):
    eligible: bool
    selected_retry_hours: float
    calibrated_probability: float
    confidence_tier: Literal["Low", "Medium", "High"]
    candidate_scores: list[CandidateScore]


class TransactionPage(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[dict]


class DatasetValidationResult(BaseModel):
    """Result of CSV validation before inference."""
    valid: bool
    record_count: int
    eligible_count: int | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class InferenceResultItem(BaseModel):
    """Single inference result for a row in the uploaded CSV."""
    transaction_id: str | None = None
    customer_id: str | None = None
    eligible: bool
    selected_retry_hours: float | None = None
    calibrated_probability: float | None = None
    confidence_tier: Literal["Low", "Medium", "High"] | None = None
    error: str | None = None


class InferenceResponse(BaseModel):
    """Batch inference results from uploaded CSV."""
    dataset_source: Literal["demo", "upload"]
    total_records: int
    eligible_records: int
    processed_records: int
    failed_records: int
    eligible_by_confidence: dict[str, int] = Field(default_factory=dict)
    avg_selected_retry_hours: float | None = None
    results: list[InferenceResultItem]
    errors: list[str] = Field(default_factory=list)
