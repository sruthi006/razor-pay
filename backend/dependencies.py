"""FastAPI dependencies for startup-loaded services."""

from fastapi import Request

from backend.services.audit_service import AuditService
from backend.services.dashboard_service import DashboardService
from backend.services.model_service import ModelService
from backend.services.simulation_service import SimulationService


def model_service(request: Request) -> ModelService:
    return request.app.state.model_service


def dashboard_service(request: Request) -> DashboardService:
    return request.app.state.dashboard_service


def simulation_service(request: Request) -> SimulationService:
    return request.app.state.simulation_service


def audit_service(request: Request) -> AuditService:
    return request.app.state.audit_service
