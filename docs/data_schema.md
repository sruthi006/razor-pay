# Synthetic dataset schema

This is the **contract** for the table Phase 2 will generate. No rows are generated in Phase 1.

**Grain:** one row = one failed payment × one candidate retry offset.  
A single `transaction_id` therefore appears multiple times (once per candidate on the prototype grid), each with its own `hours_since_failure` / `candidate_retry_hours` and `retry_success` label.

Production Razorpay payment logs are **not** available. Every column is either copied from **public error-reason names** or **synthetically generated**. Nothing below is a live merchant export.

## Target variable

| Field | Role |
| --- | --- |
| `retry_success` | **Only training/evaluation label.** 1 if a retry of this failed payment **at this candidate offset** would succeed; 0 otherwise. |

The model eventually estimates:

`P(retry_success = 1 | features available at scoring time)`

`retry_success` is **not** observed when recommending a retry. It must not be used as an input feature.

## Field dictionary

| Field | Type | Meaning | Example | Observed vs synthetic | Available at prediction time? |
| --- | --- | --- | --- | --- | --- |
| `transaction_id` | string | Synthetic failed-payment id (one original decline). Not a real Razorpay `pay_*` id. | `txn_0001842` | Synthetic | Yes (identifier only; do not encode as a numeric feature) |
| `decline_reason` | string | Razorpay public `reason` string from the Phase 1 catalog | `insufficient_funds` | Name from **public docs**; assignment of a reason to a synthetic row is **synthetic** | Yes |
| `decline_bucket` | string | Prototype retry category: `SOFT_RETRY`, `HARD_FAILURE`, `DO_NOT_RETRY` | `SOFT_RETRY` | **Synthetic business rule** (derived from `decline_reason` via `src/decline_codes.py`) | Yes (deterministic function of `decline_reason`; including both is redundant, not leakage) |
| `amount_inr` | float | Original payment amount in INR | `2499.00` | Synthetic | Yes |
| `payment_method` | string | Instrument family for this prototype (card-focused) | `card` | Synthetic | Yes |
| `failure_timestamp` | datetime (UTC or IST, documented at generation) | When the original attempt failed | `2026-03-15T21:40:00+05:30` | Synthetic | Yes |
| `hour_of_day` | int 0–23 | Hour of `failure_timestamp` (local clock used in generation) | `21` | Derived from synthetic timestamp | Yes |
| `day_of_month` | int 1–31 | Calendar day of failure | `15` | Derived | Yes |
| `day_of_week` | int 0–6 | Weekday of failure (document encoding: Monday=0 in generator code) | `6` | Derived | Yes |
| `retry_attempt_number` | int ≥ 1 | Which automatic retry this candidate represents (prototype: usually 1) | `1` | Synthetic | Yes |
| `hours_since_failure` | float | Delay between failure and this candidate retry, in hours | `24.0` | Synthetic candidate attribute | Yes **for the candidate being scored** |
| `customer_previous_success_rate` | float 0–1 | Share of this synthetic customer's prior *original* attempts that succeeded, **before** this failure | `0.72` | Synthetic history | Yes (must be lagged; see leakage) |
| `customer_previous_failure_count` | int ≥ 0 | Count of prior original failures for this customer before this payment | `3` | Synthetic history | Yes (lagged) |
| `days_since_last_successful_payment` | float | Days from last synthetic success to this failure; use a sentinel (e.g. `-1`) if none | `11.0` | Synthetic history | Yes (lagged) |
| `candidate_retry_hours` | float | Candidate offset on the prototype grid (same information as `hours_since_failure` for v1) | `24.0` | Prototype grid (not a Razorpay policy) | Yes |
| `retry_success` | int 0/1 | Whether retry at this offset succeeds | `1` | **Synthetic label** | **No — target** |

v1 keeps `hours_since_failure` and `candidate_retry_hours` equal so EDA is obvious. If a later phase models elapsed time separately from “chosen policy offset,” split them then.

## Optional columns (not required for v1)

These may be added later without changing the target definition. Still synthetic unless noted.

| Field | Type | Notes | At prediction time? |
| --- | --- | --- | --- |
| `error_source` | string | Razorpay-style `source` (`customer`, `gateway`, `issuer_bank`, …) | Yes |
| `error_step` | string | Razorpay-style `step` if we stub a payment flow | Yes |
| `error_code` | string | Razorpay-style `code` such as `BAD_REQUEST_ERROR` — only if copied from public examples, not invented | Yes |
| `customer_id` | string | Stable synthetic customer key to join history | Yes |
| `retry_timestamp` | datetime | `failure_timestamp` + candidate offset | Yes (constructed) |

Do **not** add generator internals (true latent outage end time, true salary-credit hour, RNG seed used for the label) as columns the model can see.

## Feature groups (for Phase 4)

**Allowed inputs (conceptually):**

- Decline: `decline_reason` (and optionally `decline_bucket` *or* reason, not both as if they were independent signals)
- Context: `amount_inr`, `payment_method`, `hour_of_day`, `day_of_month`, `day_of_week`
- History (lagged): `customer_previous_success_rate`, `customer_previous_failure_count`, `days_since_last_successful_payment`
- Decision variable: `hours_since_failure` / `candidate_retry_hours`
- `retry_attempt_number`

**Not inputs:** `retry_success`, any future outcomes, any latent DGP parameters.

## Leakage — do not use as features

| Leak / risk | Why it is invalid at prediction time |
| --- | --- |
| `retry_success` | **Target.** Using it is training on the answer. |
| Outcome of *other* candidate rows for the same `transaction_id` | At scoring we do not know which other offsets would have worked. Aggregates like `max(retry_success)` per transaction are leakage. |
| Realized `retry_timestamp` success flags, capture time, settlement, refund | Happen after the retry decision. |
| Any “oracle” column (`best_retry_hours`, `latent_funds_arrival_hour`, `outage_end_timestamp`) | Describes how the simulator drew the label. |
| Customer metrics that include **this** payment or later payments | History must be strictly before `failure_timestamp`. |
| `transaction_id` as a learned identifier | Overfits to row identity in synthetic data. |
| Post-policy fields (chosen offset after argmax, whether baseline also succeeded) | Created by the simulator/policy, not known when scoring a candidate. |

`decline_bucket` is a **deterministic map** of `decline_reason`. Using both is redundant, not temporal leakage. Prefer encoding `decline_reason` once.

## Row example (illustrative, not generated data)

```text
transaction_id=txn_0001842
decline_reason=insufficient_funds
decline_bucket=SOFT_RETRY
amount_inr=2499.00
payment_method=card
failure_timestamp=2026-03-15T21:40:00+05:30
hour_of_day=21
day_of_month=15
day_of_week=6
retry_attempt_number=1
hours_since_failure=24.0
customer_previous_success_rate=0.72
customer_previous_failure_count=3
days_since_last_successful_payment=11.0
candidate_retry_hours=24.0
retry_success=1   ← label only
```

## Split unit (Phase 2/4)

Split by `transaction_id` (or `customer_id`), never by randomly sampling candidate rows. Random row splits leak the same payment’s other timestamps into train and test.
