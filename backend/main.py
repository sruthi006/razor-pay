"""FastAPI application: an integration layer around validated project artifacts."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.routers import audit, dashboard, inference, prediction, simulation, transactions
from backend.services.audit_service import AuditService
from backend.services.dashboard_service import DashboardService
from backend.services.model_service import ModelService
from backend.services.simulation_service import SimulationService

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load once at startup. This uses a persisted Phase 5 scorer and never fits.
    dashboard_service = DashboardService(settings.evaluation_dir)
    model_service = ModelService(settings.calibrated_model_path)
    audit_service = AuditService(dashboard_service)
    app.state.dashboard_service = dashboard_service
    app.state.model_service = model_service
    app.state.audit_service = audit_service
    app.state.simulation_service = SimulationService(model_service, dashboard_service, audit_service)
    yield


app = FastAPI(
    title="Decline-Aware Smart Retry API",
    version="0.1.0",
    description="Simulation-only API over validated synthetic Smart Retry artifacts.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": "smart-retry-api"}


app.include_router(dashboard.router, prefix="/api")
app.include_router(prediction.router, prefix="/api")
app.include_router(simulation.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(inference.router, prefix="/api")
