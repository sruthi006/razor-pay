# Synthetic data assumptions

Phase 2 will **simulate** retry outcomes. None of the relationships below are measured on Razorpay production traffic, and **Razorpay has not confirmed them**.

They exist so the ML problem is:

1. Grounded in **public failure-reason names**
2. Structured enough that timing can matter for **some** reasons
3. Noisy enough that a model cannot memorize a deterministic rule

When documentation **does** mention customer next steps (e.g. retry after some time, wait 24 hours), we treat that as **motivation**, not as an empirical hazard function.

## Design principles

- Encode **reason-specific** timing patterns, not one global “later is better” curve.
- Keep effects **modest** plus **Bernoulli noise** so logistic regression / trees must generalize.
- Customer history and amount are **weak** covariates, not oracles.
- Hard failures: delay ≈ useless.
- Risk-tagged failures: **not** auto-retried (policy), labels unused for training.

## Intended relationships (all synthetic)

### 1. `insufficient_funds` (SOFT_RETRY)

**Assumption:** same-card retry is more likely after plausible **balance replenishment** than 15 minutes later at 21:40.

Examples we may encode (probabilistically, not as hard rules):

- Slightly higher success late morning / early evening than immediately after a night decline
- Slightly higher success around typical **salary-credit calendar days** (e.g. 1–5 or last few days of month) vs mid-month
- Larger `amount_inr` → lower retry success

Public docs say the account lacked funds and suggest another method. **Delayed same-instrument recovery is our story, not a Razorpay result.**

### 2. Temporary technical / network-style failures (SOFT_RETRY)

Reasons: `gateway_technical_error`, `bank_technical_error`, `issuer_technical_error`, `server_error`, `payment_declined_due_to_high_traffic`, and the gateway-silence subset of `payment_timed_out`.

**Assumption:** success is **higher on a short delay** (minutes–a few hours) and **does not keep rising** out to 72 hours. High-traffic declines recover as load drops, not because we waited three days.

Docs sometimes say “retry after some time.” **The shape of “some time” is synthetic.**

### 3. `transaction_daily_limit_exceeded` (SOFT_RETRY)

**Assumption:** success stays low until delay is on the order of **24 hours**, then steps up (with noise). Inspired by the public next step “wait 24 hours or use another instrument,” **not** by production curves.

### 4. `transaction_limit_exceeded` (SOFT_RETRY)

**Assumption:** weak improvement at 24–48h (credit/debit cap may not reset daily). High amounts stay hard. Distinct from the daily-limit reason.

### 5. `card_declined` (SOFT_RETRY)

**Assumption:** opaque issuer mix → **low, almost flat** success vs time. The model should not invent a sharp peak.

### 6. Hard failures (HARD_FAILURE)

Reasons such as `card_expired`, `incorrect_cvv`, `incorrect_card_details`, `debit_instrument_inactive`, `card_not_enrolled`, `debit_instrument_blocked`, `payment_cancelled`.

**Assumption:** **timing alone does not fix** instrument or credential problems. `P(retry_success)` stays near zero on every grid point. Rare 1s are noise / mislabel simulation only.

Docs typically ask for a **different card** or **correct details**. That is not a delay policy.

### 7. `payment_risk_check_failed` (DO_NOT_RETRY)

**Assumption / policy:** do not auto-retry. If present in a table for funnel completeness, labels stay unsuccessful. **Not** a documented Razorpay “never retry” flag; docs mention other cards/methods.

### 8. Customer history (modest)

**Assumption:** higher `customer_previous_success_rate` and lower `customer_previous_failure_count` slightly raise retry success for **soft** reasons. `days_since_last_successful_payment` is a weak signal (very stale customers slightly worse). Effects small vs `decline_reason` × time.

History is lagged (before this failure). **Not** claimed as a Razorpay risk score.

### 9. Amount (modest)

**Assumption:** larger `amount_inr` slightly lowers retry success, more so for funds and limit reasons. Not a cliff except as noise.

### 10. Calendar features

`hour_of_day`, `day_of_month`, `day_of_week` matter **only through the reason-specific stories above** (NSF replenishment, daily limit reset). They are not a universal “weekday lift.”

## Noise and non-determinism

The generator must:

- Draw `retry_success` from a probability, not `if hour == 10: success`
- Use overlapping curves so two reasons are not linearly separable by one feature
- Allow some soft retries to fail at the “best” offset
- Allow a small number of hard retries to succeed (label noise)

If a simple rule on `decline_reason` and a single hour bucket gets ~perfect AUC, the DGP is too clean — increase noise.

## Explicitly out of scope for the generator

- Real cardholder behaviour, issuer AML, or Razorpay Radar scores
- Switching payment method (v1 retries the **same** synthetic instrument)
- 3DS/OTP completion as a function of merchant delay
- Any statement that these elasticities match production

## Mapping to code (Phase 2)

Phase 2 should implement these as documented probability functions in `src/data_generation.py`, with a seed, and write CSV under `data/raw/` — **not** in this phase.
