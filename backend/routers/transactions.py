from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import dashboard_service
from backend.schemas import TransactionPage
from backend.services.dashboard_service import DashboardService

router = APIRouter(tags=["transactions"])


def _records(frame):
    return frame.astype(object).where(frame.notna(), None).to_dict(orient="records")


@router.get("/transactions", response_model=TransactionPage)
def list_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    decline_reason: str | None = None,
    confidence_tier: str | None = None,
    service: DashboardService = Depends(dashboard_service),
) -> dict:
    try:
        frame = service.transactions()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if decline_reason:
        frame = frame.loc[frame.decline_reason == decline_reason]
    if confidence_tier:
        frame = frame.loc[frame.smart_retry_confidence == confidence_tier]
    total = len(frame)
    start = (page - 1) * page_size
    return {"page": page, "page_size": page_size, "total": total, "items": _records(frame.iloc[start:start + page_size])}


@router.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: str, service: DashboardService = Depends(dashboard_service)) -> dict:
    try:
        frame = service.transactions()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    match = frame.loc[frame.transaction_id == transaction_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Unknown eligible transaction: {transaction_id}")
    return _records(match)[0]

