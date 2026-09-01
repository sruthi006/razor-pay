"""Prototype synthetic failed-payment generator (Phase 2A).

One output row = one failed payment × one candidate retry offset.

Reason names come from ``src.decline_codes`` (Razorpay public docs).
Success-versus-time curves are synthetic; see ``docs/synthetic_data_assumptions.md``.
Latent DGP parameters are never written to the table.

Module path: ``src/data_generation.py`` (Windows cannot host a second file
named ``data_generation.py`` beside this one).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.decline_codes import (
    DECLINE_CATALOG,
    RetryCategory,
    get_reason,
    listed_reasons,
)

# Prototype grid from docs/business_rules.md (not a Razorpay production policy).
CANDIDATE_RETRY_HOURS: tuple[float, ...] = (
    0.25,
    0.5,
    1.0,
    2.0,
    4.0,
    6.0,
    12.0,
    24.0,
    48.0,
    72.0,
)

OUTPUT_COLUMNS: tuple[str, ...] = (
    "transaction_id",
    "customer_id",
    "decline_reason",
    "decline_bucket",
    "amount_inr",
    "payment_method",
    "failure_timestamp",
    "hour_of_day",
    "day_of_month",
    "day_of_week",
    "retry_attempt_number",
    "hours_since_failure",
    "candidate_retry_hours",
    "customer_previous_success_rate",
    "customer_previous_failure_count",
    "days_since_last_successful_payment",
    "retry_success",
)

PAYMENT_METHODS: tuple[str, ...] = (
    "UPI",
    "Credit Card",
    "Debit Card",
    "Net Banking",
)

IST = timezone(timedelta(hours=5, minutes=30))

_TECHNICAL_REASONS = frozenset(
    {
        "gateway_technical_error",
        "bank_technical_error",
        "issuer_technical_error",
        "server_error",
        "payment_declined_due_to_high_traffic",
    }
)

# Transaction-level mix. Prototype frequencies, not production shares.
_REASON_WEIGHTS: dict[str, float] = {
    "insufficient_funds": 0.22,
    "card_declined": 0.11,
    "payment_timed_out": 0.08,
    "gateway_technical_error": 0.07,
    "bank_technical_error": 0.06,
    "issuer_technical_error": 0.05,
    "payment_declined_due_to_high_traffic": 0.04,
    "transaction_limit_exceeded": 0.05,
    "transaction_daily_limit_exceeded": 0.05,
    "server_error": 0.03,
    "card_expired": 0.04,
    "incorrect_cvv": 0.04,
    "incorrect_card_details": 0.03,
    "debit_instrument_inactive": 0.03,
    "card_not_enrolled": 0.02,
    "debit_instrument_blocked": 0.02,
    "payment_cancelled": 0.03,
    "payment_risk_check_failed": 0.05,
}


def _reason_probabilities() -> tuple[np.ndarray, np.ndarray]:
    reasons = np.array(listed_reasons(), dtype=object)
    catalog = set(reasons)
    missing = [r for r in catalog if r not in _REASON_WEIGHTS]
    extra = [r for r in _REASON_WEIGHTS if r not in catalog]
    if missing or extra:
        raise ValueError(f"Reason weights out of sync with catalog: {missing=} {extra=}")
    weights = np.array([_REASON_WEIGHTS[r] for r in reasons], dtype=float)
    weights /= weights.sum()
    return reasons, weights


def _sample_amount_inr(rng: np.random.Generator) -> float:
    u = rng.random()
    if u < 0.70:
        amount = float(np.clip(rng.lognormal(mean=np.log(900.0), sigma=0.65), 100.0, 5000.0))
    elif u < 0.95:
        amount = float(rng.uniform(5000.0, 20000.0))
    else:
        amount = float(rng.uniform(20000.0, 75000.0))
    return round(amount, 2)


def _sample_payment_method(rng: np.random.Generator) -> str:
    return str(rng.choice(PAYMENT_METHODS, p=np.array([0.45, 0.20, 0.25, 0.10])))


def _hour_weights() -> np.ndarray:
    w = np.ones(24, dtype=float)
    w[0:6] *= 0.35
    w[6:9] *= 0.9
    w[9:22] *= 1.8
    w[22:24] *= 0.7
    w /= w.sum()
    return w


def _sample_failure_timestamp(
    rng: np.random.Generator, start: datetime, span_days: int
) -> datetime:
    day_offset = int(rng.integers(0, span_days))
    hour = int(rng.choice(24, p=_hour_weights()))
    minute = int(rng.integers(0, 60))
    second = int(rng.integers(0, 60))
    ts = start + timedelta(days=day_offset)
    return ts.replace(hour=hour, minute=minute, second=second, microsecond=0)


def _history_factor(success_rate: float, failure_count: int, days_since: float) -> float:
    factor = 1.0 + 0.22 * (success_rate - 0.55)
    factor -= 0.012 * min(failure_count, 12)
    if days_since < 0:
        factor *= 0.94
    elif days_since > 90:
        factor *= 0.96
    elif days_since < 14:
        factor *= 1.03
    return float(np.clip(factor, 0.75, 1.25))


def _amount_penalty(amount_inr: float, scale: float) -> float:
    return float(1.0 / (1.0 + amount_inr / scale))


def _retry_success_probability(
    *,
    reason: str,
    bucket: RetryCategory,
    hours: float,
    amount_inr: float,
    success_rate: float,
    failure_count: int,
    days_since: float,
    failure_ts: datetime,
    timeout_is_abandonment: bool,
    rng: np.random.Generator,
) -> float:
    """Latent P(success). Never written to the dataset."""
    hist = _history_factor(success_rate, failure_count, days_since)
    retry_ts = failure_ts + timedelta(hours=float(hours))
    retry_hour = retry_ts.hour
    retry_dom = retry_ts.day

    if bucket == RetryCategory.DO_NOT_RETRY:
        p = 0.008 + float(rng.normal(0.0, 0.003))
        return float(np.clip(p, 0.002, 0.02))

    if bucket == RetryCategory.HARD_FAILURE:
        p = 0.015 + float(rng.normal(0.0, 0.006))
        return float(np.clip(p, 0.003, 0.04))

    if reason == "insufficient_funds":
        p = 0.16
        if 8 <= retry_hour <= 11 or 17 <= retry_hour <= 21:
            p += 0.11
        if retry_hour < 6:
            p -= 0.04
        if retry_dom <= 5 or retry_dom >= 25:
            p += 0.07
        p *= _amount_penalty(amount_inr, 11000.0)
        p *= hist
    elif reason in _TECHNICAL_REASONS:
        tau = 2.4 if reason == "payment_declined_due_to_high_traffic" else 5.0
        peak = 0.34 if reason == "payment_declined_due_to_high_traffic" else 0.38
        p = 0.10 + peak * float(np.exp(-hours / tau))
        p *= hist
    elif reason == "payment_timed_out":
        if timeout_is_abandonment:
            p = 0.045 * hist
        else:
            p = (0.10 + 0.30 * float(np.exp(-hours / 4.0))) * hist
    elif reason == "transaction_daily_limit_exceeded":
        step = 1.0 / (1.0 + np.exp(-(hours - 24.0) / 2.8))
        p = (0.07 + 0.26 * float(step)) * hist
        p *= _amount_penalty(amount_inr, 18000.0)
    elif reason == "transaction_limit_exceeded":
        step = 1.0 / (1.0 + np.exp(-(hours - 36.0) / 8.0))
        p = (0.07 + 0.07 * float(step)) * hist
        p *= _amount_penalty(amount_inr, 14000.0)
    elif reason == "card_declined":
        p = (0.085 + 0.012 * float(np.sin(hours / 11.0))) * hist
        p *= _amount_penalty(amount_inr, 25000.0)
    else:
        p = 0.08 * hist

    p *= float(rng.uniform(0.82, 1.18))
    return float(np.clip(p, 0.02, 0.72))


def generate_prototype_dataset(n_rows: int = 10_000, seed: int = 42) -> pd.DataFrame:
    """Generate ~``n_rows`` candidate-level rows (rounded down to a full retry grid)."""
    rng = np.random.default_rng(seed)
    grid = np.array(CANDIDATE_RETRY_HOURS, dtype=float)
    n_tx = max(1, int(n_rows) // len(grid))
    reasons_arr, reason_p = _reason_probabilities()

    n_customers = max(180, n_tx // 3)
    zipf_w = 1.0 / np.arange(1, n_customers + 1)
    zipf_w /= zipf_w.sum()
    customer_ids = np.array([f"cust_{i:04d}" for i in range(n_customers)])
    customer_history: dict[str, tuple[float, int, float]] = {}
    for cid in customer_ids:
        if rng.random() < 0.18:
            rate = float(np.clip(rng.beta(1.6, 4.0), 0.05, 0.95))
        else:
            rate = float(np.clip(rng.beta(5.5, 2.2), 0.05, 0.95))
        fail_count = int(min(rng.poisson(2.2), 25))
        if rng.random() < 0.12:
            days_since = -1.0
        else:
            days_since = round(float(np.clip(rng.exponential(18.0), 0.0, 400.0)), 1)
        customer_history[cid] = (round(rate, 4), fail_count, days_since)

    chosen_customers = rng.choice(customer_ids, size=n_tx, p=zipf_w)
    sampled_reasons = rng.choice(reasons_arr, size=n_tx, p=reason_p)
    methods = np.array([_sample_payment_method(rng) for _ in range(n_tx)])
    amounts = np.array([_sample_amount_inr(rng) for _ in range(n_tx)])
    start = datetime(2025, 10, 1, tzinfo=IST)
    timestamps = [_sample_failure_timestamp(rng, start, span_days=120) for _ in range(n_tx)]

    records: list[dict[str, object]] = []
    for i in range(n_tx):
        reason = str(sampled_reasons[i])
        spec = get_reason(reason)
        bucket = spec.retry_category
        cid = str(chosen_customers[i])
        rate, fail_count, days_since = customer_history[cid]
        ts = timestamps[i]
        amount = float(amounts[i])
        txn_id = f"txn_{i:06d}"
        timeout_abandon = bool(rng.random() < 0.48)

        for hours in grid:
            p = _retry_success_probability(
                reason=reason,
                bucket=bucket,
                hours=float(hours),
                amount_inr=amount,
                success_rate=rate,
                failure_count=fail_count,
                days_since=days_since,
                failure_ts=ts,
                timeout_is_abandonment=timeout_abandon,
                rng=rng,
            )
            success = int(rng.random() < p)
            records.append(
                {
                    "transaction_id": txn_id,
                    "customer_id": cid,
                    "decline_reason": reason,
                    "decline_bucket": bucket.value,
                    "amount_inr": amount,
                    "payment_method": str(methods[i]),
                    "failure_timestamp": ts.isoformat(),
                    "hour_of_day": ts.hour,
                    "day_of_month": ts.day,
                    "day_of_week": ts.weekday(),
                    "retry_attempt_number": 1,
                    "hours_since_failure": float(hours),
                    "candidate_retry_hours": float(hours),
                    "customer_previous_success_rate": rate,
                    "customer_previous_failure_count": fail_count,
                    "days_since_last_successful_payment": days_since,
                    "retry_success": success,
                }
            )

    df = pd.DataFrame.from_records(records, columns=list(OUTPUT_COLUMNS))
    unknown = set(df["decline_reason"].unique()) - set(DECLINE_CATALOG)
    if unknown:
        raise ValueError(f"Generated unknown decline reasons: {unknown}")
    extra_cols = [c for c in df.columns if c not in OUTPUT_COLUMNS]
    if extra_cols:
        raise ValueError(f"Refusing to emit non-observable columns: {extra_cols}")
    return df


def print_validation_report(df: pd.DataFrame) -> list[str]:
    """Print prototype QA stats. Returns warning strings."""
    warnings: list[str] = []
    hidden = [
        c
        for c in df.columns
        if any(token in c.lower() for token in ("latent", "oracle", "hidden", "best_retry"))
        or c.lower().endswith("_probability")
    ]
    if hidden:
        warnings.append(f"Hidden/DGP-like columns present: {hidden}")

    print("=== Prototype dataset validation ===")
    print(f"Dataset shape: {df.shape[0]} rows × {df.shape[1]} columns")
    print("\nMissing values:")
    print(df.isna().sum().to_string())

    pos = int(df["retry_success"].sum())
    n = len(df)
    print("\nTarget balance (retry_success):")
    print(df["retry_success"].value_counts().sort_index().to_string())
    print(f"Positive rate: {pos / n:.4f}")

    print("\nRows by decline_bucket:")
    print(df["decline_bucket"].value_counts().to_string())

    print("\nRows by payment_method:")
    print(df["payment_method"].value_counts().to_string())

    print("\nRetry success rate by decline_bucket:")
    by_bucket = df.groupby("decline_bucket")["retry_success"].mean()
    print(by_bucket.to_string())

    print("\nRetry success rate by candidate_retry_hours:")
    by_hours = df.groupby("candidate_retry_hours")["retry_success"].mean().sort_index()
    print(by_hours.to_string())

    print("\nAmount statistics (INR):")
    print(df["amount_inr"].describe().to_string())

    print("\nUnique transaction_id:", df["transaction_id"].nunique())
    print("Unique customer_id:", df["customer_id"].nunique())

    if bool(df.isna().any().any()):
        warnings.append("Missing values present.")
    hard_rate = float(by_bucket.get(RetryCategory.HARD_FAILURE.value, 0.0))
    risk_rate = float(by_bucket.get(RetryCategory.DO_NOT_RETRY.value, 0.0))
    soft_rate = float(by_bucket.get(RetryCategory.SOFT_RETRY.value, 0.0))
    if hard_rate > 0.06:
        warnings.append(f"HARD_FAILURE success rate looks high: {hard_rate:.3f}")
    if risk_rate > 0.04:
        warnings.append(f"DO_NOT_RETRY success rate looks high: {risk_rate:.3f}")
    if soft_rate < 0.05:
        warnings.append(f"SOFT_RETRY success rate looks very low: {soft_rate:.3f}")
    if pos == 0 or pos == n:
        warnings.append("Target is degenerate (all 0s or all 1s).")

    print("\nValidation warnings:")
    if warnings:
        for w in warnings:
            print(f"- {w}")
    else:
        print("- none")
    return warnings


def save_dataset(df: pd.DataFrame, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = df.loc[:, list(OUTPUT_COLUMNS)]
    ordered.to_csv(path, index=False)
    return path


def generate_failed_payments(n_rows: int = 10_000, seed: int = 42) -> pd.DataFrame:
    """Alias used by the Phase 0 placeholder API."""
    return generate_prototype_dataset(n_rows=n_rows, seed=seed)
