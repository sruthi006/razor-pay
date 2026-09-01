"""FastAPI application: an integration layer around validated project artifacts."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from backend.config import get_settings
from backend.routers import audit, dashboard, inference, prediction, simulation, transactions
from backend.services.audit_service import AuditService
from backend.services.dashboard_service import DashboardService
from backend.services.model_service import ModelService
from backend.services.simulation_service import SimulationService

settings = get_settings()
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "3001"))
FRONTEND_SERVER_URL = f"http://127.0.0.1:{FRONTEND_PORT}"


def _start_frontend_server() -> subprocess.Popen[str] | None:
    frontend_script = settings.project_root / "frontend" / "smart-retry-bloom-main" / "serve-production.mjs"
    if not frontend_script.exists():
        return None

    node_bin = shutil.which("node")
    if not node_bin:
        return None

    env = os.environ.copy()
    env["PORT"] = str(FRONTEND_PORT)
    return subprocess.Popen(
        [node_bin, str(frontend_script)],
        cwd=str(frontend_script.parent),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


async def _wait_for_frontend_server(timeout_seconds: float = 20.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{FRONTEND_SERVER_URL}/", timeout=1.0)
                if response.status_code < 500:
                    return
        except httpx.HTTPError:
            pass
        await asyncio.sleep(0.25)


async def _proxy_frontend_request(request: Request) -> Response:
    target_url = f"{FRONTEND_SERVER_URL}{request.url.path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    body = None
    if request.method.upper() not in {"GET", "HEAD"}:
        body = await request.body()

    async with httpx.AsyncClient() as client:
        upstream = await client.request(
            request.method,
            target_url,
            headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
            content=body,
        )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={k: v for k, v in upstream.headers.items() if k.lower() != "transfer-encoding"},
        media_type=upstream.headers.get("content-type"),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load once at startup. This uses a persisted Phase 5 scorer and never fits.
    dashboard_service = DashboardService(settings.evaluation_dir)
    model_service = ModelService(settings.calibrated_model_path)
    audit_service = AuditService(dashboard_service)
    # A fresh service starts with no active dataset; the dashboard then falls back
    # to the authoritative validated evaluation artifacts in evaluation/.
    app.state.dashboard_service = dashboard_service
    app.state.model_service = model_service
    app.state.audit_service = audit_service
    app.state.simulation_service = SimulationService(model_service, dashboard_service, audit_service)
    app.state.frontend_process = _start_frontend_server()
    if app.state.frontend_process is not None:
        await _wait_for_frontend_server()
    yield
    if getattr(app.state, "frontend_process", None) is not None and app.state.frontend_process.poll() is None:
        app.state.frontend_process.terminate()
        try:
            app.state.frontend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            app.state.frontend_process.kill()
            app.state.frontend_process.wait(timeout=5)


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


@app.middleware("http")
async def frontend_proxy_middleware(request: Request, call_next):
    if request.url.path.startswith("/api"):
        return await call_next(request)
    if request.url.path in {"/docs", "/openapi.json", "/redoc"}:
        return await call_next(request)
    if not request.url.path.startswith("/api"):
        return await _proxy_frontend_request(request)
    return await call_next(request)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": "smart-retry-api"}


app.include_router(dashboard.router, prefix="/api")
app.include_router(prediction.router, prefix="/api")
app.include_router(simulation.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(inference.router, prefix="/api")
