# Smart Retry FastAPI Backend

This is an **integration and simulation layer** over the existing validated Smart Retry artifacts. It does not retrain models, call Razorpay, or perform a live payment operation.

## Install

From the repository root:

```bash
python -m pip install -r requirements.txt
```

## Run locally

```bash
uvicorn backend.main:app --reload --port 8000
```

API base URL: `http://localhost:8000/api`  
Interactive docs: `http://localhost:8000/docs`

For a React/Lovable frontend, configure:

```text
VITE_API_BASE_URL=http://localhost:8000/api
```

The allowed development frontend origin is configurable:

```text
FRONTEND_ORIGIN=http://localhost:5173
```

Multiple explicit origins may be comma-separated. Wildcard CORS is not used.

## Endpoints

- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/business-impact`
- `GET /api/recovery-breakdown?dimension=decline_reason`
- `GET /api/retry-distribution`
- `GET /api/confidence`
- `GET /api/transactions?page=1&page_size=25`
- `GET /api/transactions/{transaction_id}`
- `GET /api/audit?transaction_id=TX000001`
- `POST /api/predict`
- `POST /api/simulate`

## Example prediction

```bash
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{
    "amount_inr": 1685.44,
    "decline_reason": "gateway_technical_error",
    "payment_method": "Credit Card",
    "hour_of_day": 12,
    "day_of_month": 9,
    "day_of_week": 3,
    "customer_previous_success_rate": 0.67,
    "customer_previous_failure_count": 1,
    "days_since_last_successful_payment": 1.34
  }'
```

The response contains the calibrated probability and confidence tier for every bounded retry candidate, plus one selected retry time.

## Simulation safety

`POST /api/simulate` is a **demo-only** endpoint. It never contacts a gateway or attempts to charge a payment instrument. For a known synthetic transaction id, it surfaces the existing Phase 6 synthetic outcome; for new input, it returns prediction-only simulation status because no observed outcome exists.
