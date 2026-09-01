import io

from fastapi.testclient import TestClient

from backend.main import app


VALID_REQUEST = {
    "amount_inr": 1685.44,
    "decline_reason": "gateway_technical_error",
    "payment_method": "Credit Card",
    "hour_of_day": 12,
    "day_of_month": 9,
    "day_of_week": 3,
    "customer_previous_success_rate": 0.6666666666666666,
    "customer_previous_failure_count": 1,
    "days_since_last_successful_payment": 1.34,
}


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "smart-retry-api"}


def test_dashboard_uses_validated_artifacts() -> None:
    with TestClient(app) as client:
        response = client.get("/api/dashboard")
    assert response.status_code == 200
    assert response.json()["eligible_transactions"] == 7471
    assert response.json()["smart_recovery_transactions"] == 3939


def test_prediction_returns_all_candidate_scores() -> None:
    with TestClient(app) as client:
        response = client.post("/api/predict", json=VALID_REQUEST)
    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is True
    assert len(body["candidate_scores"]) == 10
    assert body["confidence_tier"] in {"Low", "Medium", "High"}


def test_prediction_rejects_non_eligible_reason() -> None:
    with TestClient(app) as client:
        response = client.post("/api/predict", json={**VALID_REQUEST, "decline_reason": "card_expired"})
    assert response.status_code == 422
    assert "not eligible" in response.json()["detail"]


def test_transaction_lookup_and_simulation_are_synthetic() -> None:
    with TestClient(app) as client:
        detail = client.get("/api/transactions/TX000001")
        simulation = client.post("/api/simulate", json={**VALID_REQUEST, "transaction_id": "TX000001"})
    assert detail.status_code == 200
    assert detail.json()["transaction_id"] == "TX000001"
    assert simulation.status_code == 200
    assert simulation.json()["simulated_result"] in {"recovered", "lost"}
    assert simulation.json()["audit_events"][0]["simulated"] is True


def test_cors_accepts_configured_local_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/predict",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_upload_with_wide_observed_outcomes_is_treated_as_active_dataset() -> None:
    csv_rows = [
        {
            "transaction_id": "W1",
            "customer_id": "C1",
            "decline_reason": "gateway_technical_error",
            "decline_bucket": "SOFT_RETRY",
            "amount_inr": 1200,
            "payment_method": "Credit Card",
            "failure_timestamp": "2026-04-09 12:06:35+05:30",
            "hour_of_day": 12,
            "day_of_month": 5,
            "day_of_week": 1,
            "retry_attempt_number": 1,
            "candidate_retry_hours": 1.0,
            "customer_previous_success_rate": 0.7,
            "customer_previous_failure_count": 0,
            "days_since_last_successful_payment": 1.2,
            "fixed_retry_hours": 24,
            "smart_retry_hours": 6,
            "retry_success_1h": 0,
            "retry_success_6h": 1,
            "retry_success_12h": 1,
            "retry_success_24h": 0,
            "retry_success_48h": 0,
            "fixed_retry_success": 0,
            "smart_retry_success": 1,
            "fixed_recovered_inr": 0.0,
            "smart_recovered_inr": 1200.0,
            "observed_outcome_source": "synthetic_eval",
        },
        {
            "transaction_id": "W2",
            "customer_id": "C2",
            "decline_reason": "gateway_technical_error",
            "decline_bucket": "SOFT_RETRY",
            "amount_inr": 3400,
            "payment_method": "UPI",
            "failure_timestamp": "2026-04-10 18:20:00+05:30",
            "hour_of_day": 18,
            "day_of_month": 9,
            "day_of_week": 3,
            "retry_attempt_number": 1,
            "candidate_retry_hours": 12.0,
            "customer_previous_success_rate": 0.4,
            "customer_previous_failure_count": 1,
            "days_since_last_successful_payment": 3.0,
            "fixed_retry_hours": 48,
            "smart_retry_hours": 12,
            "retry_success_1h": 1,
            "retry_success_6h": 0,
            "retry_success_12h": 0,
            "retry_success_24h": 0,
            "retry_success_48h": 0,
            "fixed_retry_success": 1,
            "smart_retry_success": 0,
            "fixed_recovered_inr": 3400.0,
            "smart_recovered_inr": 0.0,
            "observed_outcome_source": "synthetic_eval",
        },
        {
            "transaction_id": "W3",
            "customer_id": "C3",
            "decline_reason": "gateway_technical_error",
            "decline_bucket": "SOFT_RETRY",
            "amount_inr": 880,
            "payment_method": "Debit Card",
            "failure_timestamp": "2026-04-11 08:40:00+05:30",
            "hour_of_day": 20,
            "day_of_month": 14,
            "day_of_week": 5,
            "retry_attempt_number": 1,
            "candidate_retry_hours": 24.0,
            "customer_previous_success_rate": 0.9,
            "customer_previous_failure_count": 0,
            "days_since_last_successful_payment": 5.5,
            "fixed_retry_hours": 72,
            "smart_retry_hours": 24,
            "retry_success_1h": 0,
            "retry_success_6h": 0,
            "retry_success_12h": 0,
            "retry_success_24h": 0,
            "retry_success_48h": 0,
            "fixed_retry_success": 0,
            "smart_retry_success": 0,
            "fixed_recovered_inr": 0.0,
            "smart_recovered_inr": 0.0,
            "observed_outcome_source": "synthetic_eval",
        },
    ]
    csv_buffer = io.StringIO()
    import csv
    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=list(csv_rows[0].keys()),
    )
    writer.writeheader()
    writer.writerows(csv_rows)

    with TestClient(app) as client:
        response = client.post(
            "/api/inference/upload",
            files={"file": ("wide_eval.csv", csv_buffer.getvalue(), "text/csv")},
        )

    assert response.status_code == 200
    dashboard = TestClient(app).get("/api/dashboard")
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["outcome_data_available"] is True
    assert payload["fixed_recovered_inr"] > 0
    assert payload["smart_recovered_inr"] > 0
    assert payload["incremental_recovered_inr"] != 0
