"""Demo-only workflow; never calls a payment gateway or attempts a charge."""

from __future__ import annotations

from backend.schemas import SimulationRequest
from backend.services.audit_service import AuditService
from backend.services.dashboard_service import DashboardService
from backend.services.model_service import ModelService


class SimulationService:
    def __init__(self, model: ModelService, dashboard: DashboardService, audit: AuditService) -> None:
        self.model, self.dashboard, self.audit = model, dashboard, audit

    def simulate(self, request: SimulationRequest) -> dict:
        prediction = self.model.score(request)
        transaction_id = request.transaction_id or "demo_prediction"
        existing = self.dashboard.transactions().loc[lambda frame: frame.transaction_id == transaction_id]
        if existing.empty:
            return {
                "transaction_id": transaction_id,
                "selected_retry_hours": prediction["selected_retry_hours"],
                "probability": prediction["calibrated_probability"],
                "confidence": prediction["confidence_tier"],
                "simulated_result": "prediction_only_no_observed_synthetic_outcome",
                "recovered_inr": 0.0,
                "stopping_reason": "No matching evaluated synthetic transaction; no real payment was attempted.",
                "audit_events": [{"event": "smart_retry_recommended", "timestamp": None, "simulated": True}],
            }
        row = existing.iloc[0]
        recovered = bool(row.smart_retry_success)
        return {
            "transaction_id": transaction_id,
            "selected_retry_hours": prediction["selected_retry_hours"],
            "probability": prediction["calibrated_probability"],
            "confidence": prediction["confidence_tier"],
            "simulated_result": "recovered" if recovered else "lost",
            "recovered_inr": float(row.smart_retry_recovered_inr) if recovered else 0.0,
            "stopping_reason": "Synthetic selected-candidate outcome from validated Phase 6 evaluation artifact.",
            "audit_events": self.audit.events_for(transaction_id),
        }
