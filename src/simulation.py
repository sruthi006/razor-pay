"""Phase 6 business-value simulation for fixed schedule vs smart retry.

Both policies operate on identical SOFT_RETRY transactions. The module only
uses observed labels *after* policy selection to measure outcomes; labels are
never passed into model scoring or candidate selection.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.baseline import simulate_fixed_schedule
from src.decline_codes import RetryCategory

FIXED_SCHEDULE_HOURS = frozenset({24.0, 48.0, 72.0})


def eligible_transactions(candidate_rows: pd.DataFrame) -> pd.DataFrame:
    """Return the shared SOFT_RETRY candidate population for both policies."""
    eligible = candidate_rows.loc[candidate_rows["decline_bucket"] == RetryCategory.SOFT_RETRY.value].copy()
    if eligible.empty:
        raise ValueError("No SOFT_RETRY rows available for Phase 6.")
    return eligible


def run_smart_retry(failed_payments: pd.DataFrame, calibrated_model) -> pd.DataFrame:
    """Score all candidates and select exactly one retry per eligible transaction."""
    selected = calibrated_model.select_retry_time(failed_payments)
    if selected.transaction_id.duplicated().any():
        raise ValueError("Smart Retry selection must yield one row per transaction.")
    selected = selected.copy()
    selected["smart_retry_success"] = selected["retry_success"].astype(bool)
    selected["smart_retry_recovered_inr"] = np.where(
        selected["smart_retry_success"], selected["amount_inr"].astype(float), 0.0
    )
    return selected


def build_transaction_comparison(candidate_rows: pd.DataFrame, calibrated_model) -> pd.DataFrame:
    """Create one fair, policy-comparison row per eligible transaction."""
    eligible = eligible_transactions(candidate_rows)
    baseline = simulate_fixed_schedule(eligible)
    baseline = baseline.loc[baseline["eligible_for_baseline"]].copy()
    smart = run_smart_retry(eligible, calibrated_model)
    if len(baseline) != len(smart):
        raise ValueError("Baseline and Smart Retry do not cover the same transaction count.")
    if set(baseline.transaction_id) != set(smart.transaction_id):
        raise ValueError("Baseline and Smart Retry transaction populations differ.")

    # Phase 3 outcomes intentionally contain only the fields needed for its
    # baseline. Add payment method from the original eligible decision rows.
    context = eligible.groupby("transaction_id", as_index=False)["payment_method"].first()
    baseline = baseline.merge(context, on="transaction_id", how="left", validate="one_to_one")
    baseline_columns = baseline.loc[:, [
        "transaction_id", "decline_reason", "decline_bucket", "payment_method", "amount_inr",
        "successful_retry_hours", "recovered", "recovered_inr",
    ]].rename(columns={
        "successful_retry_hours": "baseline_selected_schedule",
        "recovered": "baseline_success",
        "recovered_inr": "baseline_recovered_inr",
    })
    smart_columns = smart.loc[:, [
        "transaction_id", "candidate_retry_hours", "calibrated_probability", "confidence_tier",
        "smart_retry_success", "smart_retry_recovered_inr",
    ]].rename(columns={
        "candidate_retry_hours": "smart_retry_selected_hours",
        "calibrated_probability": "smart_retry_probability",
        "confidence_tier": "smart_retry_confidence",
    })
    comparison = baseline_columns.merge(smart_columns, on="transaction_id", validate="one_to_one")
    comparison["baseline_success"] = comparison["baseline_success"].astype(bool)
    comparison["smart_retry_success"] = comparison["smart_retry_success"].astype(bool)
    comparison["incremental_recovery_inr"] = comparison["smart_retry_recovered_inr"] - comparison["baseline_recovered_inr"]
    return comparison.sort_values("transaction_id").reset_index(drop=True)


def strategy_summary(comparison: pd.DataFrame) -> dict[str, float | int]:
    """Summarize recovery outcomes across the common eligible population."""
    n = len(comparison)
    baseline_count = int(comparison.baseline_success.sum())
    smart_count = int(comparison.smart_retry_success.sum())
    baseline_inr = float(comparison.baseline_recovered_inr.sum())
    smart_inr = float(comparison.smart_retry_recovered_inr.sum())
    return {
        "eligible_transactions": n,
        "fixed_recovered_transactions": baseline_count,
        "fixed_recovery_rate": baseline_count / n,
        "fixed_recovered_inr": baseline_inr,
        "fixed_unrecovered_inr": float(comparison.amount_inr.sum() - baseline_inr),
        "smart_recovered_transactions": smart_count,
        "smart_recovery_rate": smart_count / n,
        "smart_recovered_inr": smart_inr,
        "smart_unrecovered_inr": float(comparison.amount_inr.sum() - smart_inr),
        "incremental_recovered_transactions": smart_count - baseline_count,
        "incremental_recovery_rate": (smart_count - baseline_count) / n,
        "incremental_recovered_inr": smart_inr - baseline_inr,
        "recovered_inr_lift_pct": (smart_inr - baseline_inr) / baseline_inr if baseline_inr else 0.0,
        "fixed_average_recovered_transaction_value": baseline_inr / baseline_count if baseline_count else 0.0,
        "smart_average_recovered_transaction_value": smart_inr / smart_count if smart_count else 0.0,
    }


def breakdown(comparison: pd.DataFrame, group_column: str) -> pd.DataFrame:
    """Calculate common-population policy metrics by a single business dimension."""
    output = comparison.groupby(group_column, dropna=False).agg(
        eligible_transactions=("transaction_id", "count"),
        baseline_recovered_transactions=("baseline_success", "sum"),
        smart_retry_recovered_transactions=("smart_retry_success", "sum"),
        baseline_recovered_inr=("baseline_recovered_inr", "sum"),
        smart_retry_recovered_inr=("smart_retry_recovered_inr", "sum"),
        incremental_inr=("incremental_recovery_inr", "sum"),
    ).reset_index()
    output["baseline_recovery_rate"] = output.baseline_recovered_transactions / output.eligible_transactions
    output["smart_retry_recovery_rate"] = output.smart_retry_recovered_transactions / output.eligible_transactions
    return output.sort_values(group_column).reset_index(drop=True)


def bootstrap_strategy_difference(comparison: pd.DataFrame, n_resamples: int = 5_000, seed: int = 2026) -> dict[str, object]:
    """Transaction-level bootstrap for Smart Retry minus fixed-schedule impact."""
    baseline_success = comparison.baseline_success.to_numpy(dtype=float)
    smart_success = comparison.smart_retry_success.to_numpy(dtype=float)
    baseline_inr = comparison.baseline_recovered_inr.to_numpy(dtype=float)
    smart_inr = comparison.smart_retry_recovered_inr.to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    incremental_inr = np.empty(n_resamples)
    incremental_rate = np.empty(n_resamples)
    fixed_rates = np.empty(n_resamples)
    smart_rates = np.empty(n_resamples)
    fixed_inr = np.empty(n_resamples)
    smart_inr_samples = np.empty(n_resamples)
    n = len(comparison)
    for index in range(n_resamples):
        sampled = rng.integers(0, n, size=n)
        fixed_inr[index] = baseline_inr[sampled].sum()
        smart_inr_samples[index] = smart_inr[sampled].sum()
        incremental_inr[index] = smart_inr_samples[index] - fixed_inr[index]
        fixed_rates[index] = baseline_success[sampled].mean()
        smart_rates[index] = smart_success[sampled].mean()
        incremental_rate[index] = smart_rates[index] - fixed_rates[index]
    def interval(values: np.ndarray) -> list[float]:
        return [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]
    return {
        "method": "transaction-level bootstrap with replacement",
        "n_resamples": n_resamples,
        "incremental_recovered_inr_ci_95": interval(incremental_inr),
        "incremental_recovery_rate_ci_95": interval(incremental_rate),
        "fixed_recovered_inr_ci_95": interval(fixed_inr),
        "smart_retry_recovered_inr_ci_95": interval(smart_inr_samples),
        "probability_smart_retry_inr_greater_than_fixed": float((incremental_inr > 0).mean()),
        "probability_smart_retry_recovery_rate_greater_than_fixed": float((incremental_rate > 0).mean()),
    }
