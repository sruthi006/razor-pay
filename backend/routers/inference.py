"""Inference endpoints for CSV upload and batch predictions."""

from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from backend.schemas import DatasetValidationResult, InferenceResponse
from backend.dependencies import dashboard_service, model_service
from backend.services.dashboard_service import DashboardService
from backend.services.model_service import ModelService
from backend.services.inference_service import InferenceService

router = APIRouter(tags=["inference"])


def _comparison_when_outcomes_are_complete(rows: pd.DataFrame, svc: ModelService):
    """Support both the legacy candidate-grid schema and the wide synthetic evaluation format.

    The uploaded synthetic evaluation CSV is valid observed-outcome data even
    though it is stored in wide columns rather than one row per candidate time.
    """
    return DashboardService._comparison_from_uploaded_rows(rows, svc._model)


@router.post("/inference/validate-csv", response_model=DatasetValidationResult)
async def validate_csv(
    file: UploadFile = File(...),
) -> dict:
    """
    Validate a CSV file without running inference.

    Returns validation status and column checks.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are accepted",
        )

    try:
        contents = await file.read()
        import io
        import pandas as pd

        csv_content = io.BytesIO(contents)
        df = pd.read_csv(csv_content)

        if df.empty:
            return {
                "valid": False,
                "record_count": 0,
                "errors": ["CSV file is empty"],
            }

        from src.model import FEATURE_COLUMNS

        required_cols = set(FEATURE_COLUMNS)
        missing_cols = required_cols - set(df.columns)

        if missing_cols:
            return {
                "valid": False,
                "record_count": len(df),
                "errors": [
                    f"Missing required columns: {sorted(missing_cols)}",
                ],
            }

        return {
            "valid": True,
            "record_count": len(df),
            "eligible_count": None,
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to validate CSV: {str(e)}",
        )


@router.post("/inference/upload", response_model=InferenceResponse)
async def upload_and_infer(
    file: UploadFile = File(...),
    svc: ModelService = Depends(model_service),
    dashboard: DashboardService = Depends(dashboard_service),
) -> dict:
    """
    Upload a CSV file and run batch inference using the trained model.

    The uploaded CSV must contain these columns:
    - amount_inr (float)
    - decline_reason (string)
    - payment_method (string: UPI, Credit Card, Debit Card, Net Banking)
    - hour_of_day (int, 0-23)
    - day_of_month (int, 1-31)
    - day_of_week (int, 0-6)
    - customer_previous_success_rate (float, 0-1)
    - customer_previous_failure_count (int)
    - days_since_last_successful_payment (float)

    Optional columns:
    - transaction_id (string)
    - customer_id (string)

    The model will NOT be retrained. Inference uses the existing calibrated model.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are accepted",
        )

    try:
        contents = await file.read()
        rows = pd.read_csv(io.BytesIO(contents))
        csv_content = io.BytesIO(contents)
        inference_svc = InferenceService(svc)
        result = inference_svc.infer_from_csv_content(
            csv_content, dataset_source="upload"
        )

        if result.errors:
            raise HTTPException(
                status_code=400,
                detail=f"Inference failed: {'; '.join(result.errors)}",
            )

        dashboard.activate_dataset(
            source="upload",
            raw_rows=rows,
            inference=result.model_dump(),
            comparison=_comparison_when_outcomes_are_complete(rows, svc),
        )
        return result.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload processing error: {str(e)}",
        )


@router.get("/inference/demo", response_model=InferenceResponse)
async def load_demo_dataset(
    svc: ModelService = Depends(model_service),
    dashboard: DashboardService = Depends(dashboard_service),
) -> dict:
    """
    Load the demo dataset and run inference using the trained model.

    This uses the project's synthetic evaluation dataset (100k rows)
    without retraining the model.
    """
    from backend.config import get_settings

    settings = get_settings()
    demo_path = settings.source_dataset_path

    try:
        rows = pd.read_csv(demo_path)
        inference_svc = InferenceService(svc)
        result = inference_svc.infer_from_demo_dataset(demo_path)

        if result.errors:
            raise HTTPException(
                status_code=500,
                detail=f"Demo inference failed: {'; '.join(result.errors)}",
            )

        # Preserve the project's validated demo simulation exactly while still
        # making the selected demo dataset the active session dataset.
        dashboard.activate_dataset(
            source="demo",
            raw_rows=rows,
            inference=result.model_dump(),
            comparison=dashboard.evaluation_transactions(),
        )
        return result.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Demo dataset error: {str(e)}",
        )
