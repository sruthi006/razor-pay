# Decline-Aware Smart Retry Engine for Failed Payments

Portfolio project: predict **when** to retry a failed payment instead of using a fixed T+1 / T+2 / T+3 schedule.

## Objective

When a payment fails, a naive retry policy hits every failed transaction on the same calendar offsets. That wastes retries on declines that will not recover (e.g. invalid card) and misses better windows for recoverable declines (e.g. insufficient funds later in the month).

**Data limitation.** This repo does **not** have production Razorpay transaction-level retry logs. The eventual training table will be **synthetic**. Failure **reason names** and descriptions are taken from [Razorpay public error documentation](https://razorpay.com/docs/errors/) (especially [error reasons](https://razorpay.com/docs/errors/reasons/) and [cards error codes](https://razorpay.com/docs/errors/payments/cards/)). Retry buckets, candidate timestamps, and success-vs-time curves are **documented project assumptions**, not Razorpay production behaviour. See `docs/synthetic_data_assumptions.md`.

This project uses that synthetic table to:

1. Score candidate retry timestamps for each failed payment.
2. Pick the timestamp with the highest predicted success probability.
3. Compare that policy to a fixed T+1 / T+2 / T+3 baseline.
4. Attach a simple confidence score to each recommendation.
5. Visualize recovery, recovered amount (INR), and a failed → retried → recovered → lost funnel.

## Problem framing

For a failed payment \(i\) and a candidate retry time \(t\):

\[
P(\text{retry succeeds} \mid \text{decline reason}, \text{context}, t)
\]

The engine evaluates a small set of candidate times (for example hours or days after the original failure) and selects \(\arg\max_t\) of the predicted probability, subject to business rules (do not retry hard declines; cap retries).

## Planned architecture

Keep four modules. Phase 1 is scaffolding only; later phases fill these in.

```
Failed payment
      │
      ▼
Decline code rules  ──►  skip (DO_NOT_RETRY) / cap (HARD) / score times (SOFT)
      │
      ▼
Candidate retry grid  (prototype: +15m … +72h; not a Razorpay policy)
      │
      ▼
ML model  ──►  P(success | features, t)  for each candidate
      │
      ▼
Confidence layer  ──►  how much to trust this score
      │
      ▼
Policy  ──►  chosen retry time  vs  fixed T+1/T+2/T+3 baseline
      │
      ▼
Simulation + dashboard  (recovery rate, INR recovered, funnel)
```

| Module | Role |
| --- | --- |
| **Core ML model** | Predict retry success probability at a given time; pick the best candidate timestamp. |
| **Baseline** | Simulate a **prototype** fixed T+1 / T+2 / T+3 schedule on the same synthetic failures (not claimed as Razorpay’s live policy). |
| **Confidence** | Confidence from sample counts (and optional probability calibration later). |
| **Dashboard** | Streamlit views for recovery, INR, strategy comparison, funnel, and production caveats. |

## Tech stack

- Python, pandas, numpy, scikit-learn
- matplotlib / seaborn for analysis
- XGBoost only if a later phase shows a clear gain over a simpler model
- Streamlit for the dashboard
- Jupyter notebooks for exploration

No extra serving frameworks, queues, or cloud lock-in for this portfolio version.

## Repository layout

```
data/          synthetic datasets (generated in a later phase)
notebooks/     EDA and model experiments
src/           library code (decline codes, data gen, model, simulation, …)
models/        saved trained artifacts
evaluation/    metrics, comparison tables, plots
dashboard/     Streamlit app (later phase)
docs/          taxonomy notes, schema, business rules, synthetic assumptions
```

## Current status

**Phase 1 — domain grounding (in progress).** Public Razorpay `reason` taxonomy, dataset schema, prototype business rules, and explicit synthetic assumptions.

**Not done:** generating CSV rows, training, baseline simulation, evaluation, or dashboard.

## Suggested build order

1. Decline-code taxonomy and retry eligibility rules.
2. Synthetic data generator (failed payments + delayed retry outcomes).
3. Fixed-schedule baseline simulation.
4. Feature set + first sklearn model (logistic regression or gradient boosting).
5. Confidence layer.
6. Head-to-head simulation (baseline vs smart retry).
7. Streamlit dashboard and production-readiness notes.

## Disclaimer

This is an educational / interview project. It is **not** a production payments system, does not use real customer or card data, and must not be read as Razorpay’s retry engine or risk policy.
