# Prototype business rules

These rules apply to **this interview/portfolio engine**. They are **not** Razorpay’s production retry policy. Public Razorpay docs describe customer next steps (try another card, wait 24 hours, retry after some time, etc.); they do not publish a merchant T+1/T+2/T+3 or candidate-hour grid.

The comparison baseline used later (fixed T+1 / T+2 / T+3) is also a **prototype strawman**, not a documented Razorpay schedule.

## 1. Unit of decision

A **failed payment** (`transaction_id`) may be paired with **multiple candidate retry timestamps**.

The model scores each candidate independently:

\[
P(\texttt{retry\_success}=1 \mid \text{transaction context}, \text{candidate retry time})
\]

The policy selects the eligible candidate with the **highest predicted probability** (ties: earliest offset).

## 2. Eligibility by decline category

Categories live in `src/decline_codes.py`. Names of `reason` values come from [Razorpay error reasons](https://razorpay.com/docs/errors/reasons/) and [cards error codes](https://razorpay.com/docs/errors/payments/cards/). **Buckets are ours** except where noted in that file.

| `retry_category` | Automatic retry? | Timing search on the candidate grid? |
| --- | --- | --- |
| `SOFT_RETRY` | Yes | Yes — this is the ML use case |
| `HARD_FAILURE` | At most a **limited** retry (see cap below) | **No** — do not pick an “optimal hour”; timing is not the fix |
| `DO_NOT_RETRY` | **No** | **No** — exclude from recommendations and from smart-retry simulation |

`DO_NOT_RETRY` in v1 is only `payment_risk_check_failed`, as a **synthetic** rule: public docs still mention trying a different card; this prototype will not auto-retry a risk/fraud-tagged failure on the same instrument.

## 3. Retry caps (prototype)

| Category | Max automatic retries | Rationale |
| --- | --- | --- |
| `SOFT_RETRY` | 1 in v1 simulation (one chosen offset per failure) | Keeps the ML problem = “when”, not “how many” |
| `HARD_FAILURE` | 0 on the smart path; baseline may still “attempt” once only if we need a like-for-like comparison — **default: 0 smart retries, optional single retry at +24h for ablation** | Timing will not fix CVV/expiry; unlimited retries are wasteful |
| `DO_NOT_RETRY` | 0 | Risk/fraud-style failures |

v1 default: **smart retry only for `SOFT_RETRY`**. Hard and do-not-retry contribute to the funnel as failed → not retried (or retried only under an explicit ablation flag).

## 4. Candidate retry grid (prototype)

Bounded offsets from `failure_timestamp`. Not production policy.

| Offset | `candidate_retry_hours` |
| --- | ---: |
| +15 minutes | 0.25 |
| +30 minutes | 0.50 |
| +1 hour | 1 |
| +2 hours | 2 |
| +4 hours | 4 |
| +6 hours | 6 |
| +12 hours | 12 |
| +24 hours | 24 |
| +48 hours | 48 |
| +72 hours | 72 |

Rules:

- Do **not** score arbitrary timestamps outside this grid.
- Do **not** retry before +15 minutes in v1 (no immediate hammering).
- Do **not** retry after +72 hours in v1 (label window closes; unpaid amount is **lost** for funnel metrics).

## 5. Baseline comparison (later phase)

The **fixed schedule** baseline will retry eligible soft failures at **T+1 day, T+2 days, and T+3 days** as a simple control — i.e. 24h / 48h / 72h — **not** claimed as Razorpay’s live policy.

Fair comparison:

- Same synthetic failures
- Same eligibility (`SOFT_RETRY` only unless an ablation says otherwise)
- Same maximum of one **successful** recovery counted per `transaction_id` (first success wins; do not triple-count INR)

## 6. Funnel definitions (for later dashboard)

| Stage | Meaning in this prototype |
| --- | --- |
| Failed | Original attempt failed |
| Retried | Policy scheduled at least one retry |
| Recovered | At least one retry succeeded within 72h (`retry_success=1` at the chosen offset) |
| Lost | Not recovered within the window (including never retried) |

Recovered amount = `amount_inr` of recovered `transaction_id`s, counted once.

## 7. Model constraints (later)

- Train only on rows that would have been **eligible** to score (`SOFT_RETRY`), unless an experiment explicitly studies hard-fail calibration.
- Features: schema “allowed inputs” only; never `retry_success` or oracle columns (`docs/data_schema.md`).
- Confidence layer is separate from the probability head.

## 8. What we will not claim

- That Razorpay retries on this grid or on T+1/T+2/T+3
- That `DO_NOT_RETRY` is an official Razorpay error flag
- That optimizing delay replaces customer actions (correct CVV, new card, complete OTP)
