"""Audit views sourced from existing simulation artifacts; no fabricated times."""

from __future__ import annotations

from backend.services.dashboard_service import DashboardService


class AuditService:
    def __init__(self, dashboard: DashboardService) -> None:
        self.dashboard = dashboard

    def events_for(self, transaction_id: str) -> list[dict]:
        return self.dashboard.audit_events(transaction_id)
