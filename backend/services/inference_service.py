"""Batch inference on uploaded datasets using the existing trained model."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from backend.schemas import InferenceResponse, InferenceResultItem
from src.decline_codes import allows_timing_optimization
from src.model import FEATURE_COLUMNS, load_and_validate_model_data
from backend.services.model_service import ModelService


class InferenceService:
    """Run batch inference on uploaded or demo datasets without retraining."""

    def __init__(self, model_service: ModelService) -> None:
        self.model_service = model_service

    def infer_from_csv_content(
        self,
        csv_content: io.BytesIO,
        dataset_source: str = "upload",
    ) -> InferenceResponse:
        """
        Process uploaded CSV file and run inference.

        Args:
            csv_content: File-like object with CSV data
            dataset_source: "demo" or "upload" for UI labeling

        Returns:
            InferenceResponse with results and statistics
        """
        try:
            df = pd.read_csv(csv_content)
        except Exception as e:
            return InferenceResponse(
                dataset_source=dataset_source,
                total_records=0,
                eligible_records=0,
                processed_records=0,
                failed_records=0,
                results=[],
                errors=[f"Failed to read CSV: {str(e)}"],
            )

        # Validate required columns
        required_cols = set(FEATURE_COLUMNS)
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            return InferenceResponse(
                dataset_source=dataset_source,
                total_records=len(df),
                eligible_records=0,
                processed_records=0,
                failed_records=len(df),
                results=[],
                errors=[
                    f"Missing required columns: {sorted(missing_cols)}",
                    f"Expected columns: {sorted(required_cols)}",
                ],
            )

        # Check for empty dataset
        if df.empty:
            return InferenceResponse(
                dataset_source=dataset_source,
                total_records=0,
                eligible_records=0,
                processed_records=0,
                failed_records=0,
                results=[],
                errors=["Dataset is empty"],
            )

        # Run inference on each row
        results: list[InferenceResultItem] = []
        eligible_count = 0
        processed_count = 0
        failed_count = 0
        eligible_by_confidence: dict[str, int] = {"Low": 0, "Medium": 0, "High": 0}
        selected_retry_hours_list = []

        for idx, row in df.iterrows():
            try:
                # Extract required fields
                amount_inr = float(row.get("amount_inr", 0))
                decline_reason = str(row.get("decline_reason", "")).strip().lower()
                payment_method = str(row.get("payment_method", "")).strip()
                hour_of_day = int(row.get("hour_of_day", 12))
                day_of_month = int(row.get("day_of_month", 1))
                day_of_week = int(row.get("day_of_week", 0))
                customer_previous_success_rate = float(row.get("customer_previous_success_rate", 0.5))
                customer_previous_failure_count = int(row.get("customer_previous_failure_count", 0))
                days_since_last_successful_payment = float(row.get("days_since_last_successful_payment", 0))

                transaction_id = row.get("transaction_id")
                customer_id = row.get("customer_id")

                # Validate eligibility
                try:
                    eligible = allows_timing_optimization(decline_reason)
                except KeyError:
                    results.append(
                        InferenceResultItem(
                            transaction_id=transaction_id,
                            customer_id=customer_id,
                            eligible=False,
                            error=f"Unknown decline_reason: {decline_reason}",
                        )
                    )
                    failed_count += 1
                    continue

                if not eligible:
                    results.append(
                        InferenceResultItem(
                            transaction_id=transaction_id,
                            customer_id=customer_id,
                            eligible=False,
                            error="Decline reason not eligible for Smart Retry",
                        )
                    )
                    failed_count += 1
                    continue

                # Score using model service
                try:
                    from backend.schemas import PredictionRequest

                    pred_request = PredictionRequest(
                        amount_inr=amount_inr,
                        decline_reason=decline_reason,
                        payment_method=payment_method,
                        hour_of_day=hour_of_day,
                        day_of_month=day_of_month,
                        day_of_week=day_of_week,
                        customer_previous_success_rate=customer_previous_success_rate,
                        customer_previous_failure_count=customer_previous_failure_count,
                        days_since_last_successful_payment=days_since_last_successful_payment,
                    )
                    prediction = self.model_service.score(pred_request)

                    results.append(
                        InferenceResultItem(
                            transaction_id=transaction_id,
                            customer_id=customer_id,
                            eligible=prediction["eligible"],
                            selected_retry_hours=prediction["selected_retry_hours"],
                            calibrated_probability=prediction["calibrated_probability"],
                            confidence_tier=prediction["confidence_tier"],
                        )
                    )
                    processed_count += 1
                    eligible_count += 1
                    eligible_by_confidence[prediction["confidence_tier"]] += 1
                    selected_retry_hours_list.append(prediction["selected_retry_hours"])

                except Exception as e:
                    results.append(
                        InferenceResultItem(
                            transaction_id=transaction_id,
                            customer_id=customer_id,
                            eligible=False,
                            error=f"Scoring error: {str(e)}",
                        )
                    )
                    failed_count += 1

            except Exception as e:
                results.append(
                    InferenceResultItem(
                        transaction_id=row.get("transaction_id"),
                        customer_id=row.get("customer_id"),
                        eligible=False,
                        error=f"Row processing error: {str(e)}",
                    )
                )
                failed_count += 1

        avg_retry_hours = (
            sum(selected_retry_hours_list) / len(selected_retry_hours_list)
            if selected_retry_hours_list
            else None
        )

        return InferenceResponse(
            dataset_source=dataset_source,
            total_records=len(df),
            eligible_records=eligible_count,
            processed_records=processed_count,
            failed_records=failed_count,
            eligible_by_confidence=eligible_by_confidence,
            avg_selected_retry_hours=avg_retry_hours,
            results=results,
        )

    def infer_from_demo_dataset(self, demo_path: Path) -> InferenceResponse:
        """
        Run inference on the demo dataset.

        Args:
            demo_path: Path to demo CSV file

        Returns:
            InferenceResponse with demo results
        """
        try:
            with open(demo_path, "rb") as f:
                csv_content = io.BytesIO(f.read())
        except FileNotFoundError:
            return InferenceResponse(
                dataset_source="demo",
                total_records=0,
                eligible_records=0,
                processed_records=0,
                failed_records=0,
                results=[],
                errors=[f"Demo dataset not found: {demo_path}"],
            )

        return self.infer_from_csv_content(csv_content, dataset_source="demo")
