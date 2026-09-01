"""Load and use the validated calibrated scorer without ML retraining."""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from backend.schemas import PredictionRequest
from src.data_generation import CANDIDATE_RETRY_HOURS
from src.decline_codes import allows_timing_optimization, get_reason


class ModelService:
    def __init__(self, model_path: Path) -> None:
        if not model_path.is_file():
            raise FileNotFoundError(f"Calibrated model artifact is missing: {model_path}")
        self._model = joblib.load(model_path)

    def score(self, request: PredictionRequest) -> dict:
        try:
            eligible = allows_timing_optimization(request.decline_reason)
        except KeyError as exc:
            raise ValueError(f"Unknown decline_reason: {request.decline_reason}") from exc
        if not eligible:
            category = get_reason(request.decline_reason).retry_category.value
            raise PermissionError(f"Decline reason is not eligible for Smart Retry (category: {category}).")

        rows = []
        for attempt_number, hours in enumerate(CANDIDATE_RETRY_HOURS, start=1):
            rows.append({
                "transaction_id": "api_prediction",
                "customer_id": "api_customer",
                "decline_reason": request.decline_reason,
                "decline_bucket": "SOFT_RETRY",
                "amount_inr": request.amount_inr,
                "payment_method": request.payment_method,
                "failure_timestamp": "",  # not a model feature
                "hour_of_day": request.hour_of_day,
                "day_of_month": request.day_of_month,
                "day_of_week": request.day_of_week,
                "retry_attempt_number": attempt_number,
                "candidate_retry_hours": float(hours),
                "customer_previous_success_rate": request.customer_previous_success_rate,
                "customer_previous_failure_count": request.customer_previous_failure_count,
                "days_since_last_successful_payment": request.days_since_last_successful_payment,
            })
        candidates = self._model.score_candidates(pd.DataFrame(rows))
        selected = self._model.select_retry_time(pd.DataFrame(rows)).iloc[0]
        scores = candidates.loc[:, ["candidate_retry_hours", "calibrated_probability", "confidence_tier"]]
        return {
            "eligible": True,
            "selected_retry_hours": float(selected["candidate_retry_hours"]),
            "calibrated_probability": float(selected["calibrated_probability"]),
            "confidence_tier": str(selected["confidence_tier"]),
            "candidate_scores": [
                {
                    "candidate_retry_hours": float(row.candidate_retry_hours),
                    "calibrated_probability": float(row.calibrated_probability),
                    "confidence_tier": str(row.confidence_tier),
                }
                for row in scores.itertuples(index=False)
            ],
        }

    def build_transaction_comparison(self, candidate_rows: pd.DataFrame) -> pd.DataFrame:
        """Evaluate observed candidate outcomes with the already-loaded scorer."""
        from src.simulation import build_transaction_comparison

        return build_transaction_comparison(candidate_rows, self._model)
