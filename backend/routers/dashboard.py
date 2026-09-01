from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import dashboard_service
from backend.services.dashboard_service import DashboardService

router = APIRouter(tags=["dashboard"])


def _artifact_error(exc: FileNotFoundError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


@router.get("/dashboard")
def get_dashboard(service: DashboardService = Depends(dashboard_service)) -> dict:
    try:
        return service.dashboard()
    except FileNotFoundError as exc:
        raise _artifact_error(exc) from exc


@router.get("/business-impact")
def get_business_impact(service: DashboardService = Depends(dashboard_service)) -> dict:
    try:
        return service.business_impact()
    except FileNotFoundError as exc:
        raise _artifact_error(exc) from exc


@router.get("/recovery-breakdown")
def get_recovery_breakdown(dimension: str, service: DashboardService = Depends(dashboard_service)) -> dict:
    try:
        return {"dimension": dimension, "items": service.breakdown(dimension)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise _artifact_error(exc) from exc


@router.get("/retry-distribution")
def get_retry_distribution(service: DashboardService = Depends(dashboard_service)) -> dict:
    try:
        return service.retry_distribution()
    except FileNotFoundError as exc:
        raise _artifact_error(exc) from exc


@router.get("/confidence")
def get_confidence(service: DashboardService = Depends(dashboard_service)) -> dict:
    try:
        return {"tiers": service.confidence()}
    except FileNotFoundError as exc:
        raise _artifact_error(exc) from exc
