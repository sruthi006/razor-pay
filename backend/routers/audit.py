"""Dedicated audit endpoint for simulation/evaluation-derived events."""

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import audit_service
from backend.services.audit_service import AuditService

router = APIRouter(tags=["audit"])


@router.get("/audit")
def get_audit(transaction_id: str = Query(..., min_length=1), service: AuditService = Depends(audit_service)) -> dict:
    try:
        return {"transaction_id": transaction_id, "events": service.events_for(transaction_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
