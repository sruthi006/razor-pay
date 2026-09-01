"""Phase 3 fixed-schedule baseline: retry eligible failures at T+1/T+2/T+3.

This is a project control policy, not a claim about Razorpay's production
retry schedule. It uses only 24, 48 and 72 hour candidate rows and never
edits the source dataset.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.decline_codes import RetryCategory, retry_category_for


FIXED_RETRY_HOURS: tuple[float, ...] = (24.0, 48.0, 72.0)

# ``hours_since_failure`` is deliberately not required: the authoritative
# corrected Phase 2 dataset uses candidate_retry_hours as the one time field.
REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
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
        "candidate_retry_hours",
        "customer_previous_success_rate",
        "customer_previous_failure_count",
        "days_since_last_successful_payment",
        "retry_success",
    }
)

TRANSACTION_CONSTANT_COLUMNS: tuple[str, ...] = (
    "customer_id",
    "decline_reason",
    "decline_bucket",
    "amount_inr",
    "payment_method",
    "failure_timestamp",
)


def load_and_validate_dataset(path: str | Path) -> tuple[pd.DataFrame, list[str]]:
    """Load the authoritative CSV and validate baseline prerequisites.

    Returns the unmodified data frame and non-fatal schema warnings. Invalid
    data raises ``ValueError`` rather than silently producing a baseline.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Baseline input dataset not found: {path}")

    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")
    if df.empty:
        raise ValueError("Dataset is empty.")
    if df[list(REQUIRED_COLUMNS)].isna().any().any():
        null_columns = df[list(REQUIRED_COLUMNS)].columns[df[list(REQUIRED_COLUMNS)].isna().any()]
        raise ValueError(f"Required columns contain nulls: {list(null_columns)}")
    if not df["retry_success"].isin([0, 1]).all():
        raise ValueError("retry_success must contain only 0 and 1.")

    candidate_hours = pd.to_numeric(df["candidate_retry_hours"], errors="coerce")
    if candidate_hours.isna().any():
        raise ValueError("candidate_retry_hours must be numeric.")
    df = df.copy()
    df["candidate_retry_hours"] = candidate_hours.astype(float)
    if not set(FIXED_RETRY_HOURS).issubset(set(df["candidate_retry_hours"].unique())):
        raise ValueError(f"Dataset lacks one or more fixed offsets: {FIXED_RETRY_HOURS}")
    if df.duplicated(["transaction_id", "candidate_retry_hours"]).any():
        raise ValueError("Duplicate transaction_id/candidate_retry_hours rows found.")

    unknown_reasons = sorted(set(df["decline_reason"]) - {
        reason for reason in df["decline_reason"].unique() if _known_reason(reason)
    })
    if unknown_reasons:
        raise ValueError(f"Unknown decline reasons not in catalog: {unknown_reasons}")

    expected_bucket = df["decline_reason"].map(lambda value: retry_category_for(value).value)
    mismatch = df["decline_bucket"] != expected_bucket
    if mismatch.any():
        examples = df.loc[mismatch, ["decline_reason", "decline_bucket"]].drop_duplicates().to_dict("records")
        raise ValueError(f"decline_bucket conflicts with catalog: {examples}")

    nonconstant = [
        column
        for column in TRANSACTION_CONSTANT_COLUMNS
        if (df.groupby("transaction_id")[column].nunique(dropna=False) > 1).any()
    ]
    if nonconstant:
        raise ValueError(f"Transaction context changes across candidate rows: {nonconstant}")

    warnings: list[str] = []
    if "hours_since_failure" not in df.columns:
        warnings.append(
            "Authoritative dataset does not contain hours_since_failure; "
            "candidate_retry_hours is used as the documented v1 time feature."
        )
    per_transaction_offsets = df.groupby("transaction_id")["candidate_retry_hours"].nunique()
    if (per_transaction_offsets < len(FIXED_RETRY_HOURS)).any():
        raise ValueError("At least one transaction lacks a required fixed retry offset.")
    return df, warnings


def _known_reason(reason: str) -> bool:
    try:
        retry_category_for(reason)
    except KeyError:
        return False
    return True


def assign_fixed_retry_times(failed_payments: pd.DataFrame) -> pd.DataFrame:
    """Return only the chronological T+1/T+2/T+3 candidate opportunities."""
    scheduled = failed_payments.loc[
        failed_payments["candidate_retry_hours"].isin(FIXED_RETRY_HOURS)
    ].copy()
    return scheduled.sort_values(["transaction_id", "candidate_retry_hours"])


def simulate_fixed_schedule(failed_payments: pd.DataFrame) -> pd.DataFrame:
    """Apply T+1/T+2/T+3 to SOFT_RETRY transactions, first success wins.

    The outcome has exactly one row per original failed transaction. HARD and
    DO_NOT_RETRY transactions are retained as ``not_eligible`` and count as
    lost in the all-failed funnel, per the existing business rules.
    """
    scheduled = assign_fixed_retry_times(failed_payments)
    records: list[dict[str, object]] = []

    for transaction_id, transaction_rows in scheduled.groupby("transaction_id", sort=True):
        first = transaction_rows.iloc[0]
        is_eligible = first["decline_bucket"] == RetryCategory.SOFT_RETRY.value
        all_scheduled_attempts = transaction_rows if is_eligible else transaction_rows.iloc[0:0]
        attempted_retry_count = 0
        successful_offset: float | None = None
        # Scan the schedule in time order and stop immediately on recovery.
        # Later potential-outcome labels are not treated as attempted retries.
        for row in all_scheduled_attempts.itertuples(index=False):
            attempted_retry_count += 1
            if row.retry_success == 1:
                successful_offset = float(row.candidate_retry_hours)
                break
        recovered = successful_offset is not None
        amount = float(first["amount_inr"])

        records.append(
            {
                "transaction_id": transaction_id,
                "customer_id": first["customer_id"],
                "decline_reason": first["decline_reason"],
                "decline_bucket": first["decline_bucket"],
                "amount_inr": amount,
                "eligible_for_baseline": bool(is_eligible),
                "scheduled_retry_hours": "24|48|72" if is_eligible else "",
                "attempted_retry_count": attempted_retry_count,
                "recovered": bool(recovered),
                "successful_retry_hours": successful_offset,
                "recovery_status": "recovered" if recovered else ("lost" if is_eligible else "not_eligible"),
                "recovered_inr": amount if recovered else 0.0,
                "lost_inr": 0.0 if recovered else amount,
            }
        )

    outcomes = pd.DataFrame.from_records(records)
    if outcomes["transaction_id"].duplicated().any():
        raise ValueError("Baseline outcome must have one row per transaction.")
    if (outcomes["attempted_retry_count"] > len(FIXED_RETRY_HOURS)).any():
        raise ValueError("A transaction exceeded the fixed retry cap.")
    return outcomes


def summarize_baseline(outcomes: pd.DataFrame) -> pd.DataFrame:
    """Create concise, auditable fixed-baseline metrics."""
    total = len(outcomes)
    eligible = outcomes["eligible_for_baseline"]
    recovered = outcomes["recovered"]
    eligible_count = int(eligible.sum())
    recovered_count = int(recovered.sum())
    unrecovered_count = int((~recovered).sum())
    eligible_unrecovered = int((eligible & ~recovered).sum())
    recovered_inr = float(outcomes["recovered_inr"].sum())
    lost_inr = float(outcomes["lost_inr"].sum())

    metrics = [
        ("total_failed_transactions", total),
        ("eligible_soft_retry_transactions", eligible_count),
        ("recovered_transactions", recovered_count),
        ("unrecovered_lost_transactions_all_failed", unrecovered_count),
        ("unrecovered_lost_transactions_eligible", eligible_unrecovered),
        ("recovered_inr", recovered_inr),
        ("unrecovered_lost_inr_all_failed", lost_inr),
        ("recovery_rate_eligible", recovered_count / eligible_count if eligible_count else 0.0),
        ("recovery_rate_all_failed", recovered_count / total if total else 0.0),
    ]
    return pd.DataFrame(metrics, columns=["metric", "value"])


def save_baseline_artifacts(
    outcomes: pd.DataFrame,
    metrics: pd.DataFrame,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Save only derived Phase 3 artifacts; source data remains untouched."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outcomes_path = output_dir / "fixed_schedule_baseline_outcomes.csv"
    metrics_path = output_dir / "fixed_schedule_baseline_summary.csv"
    outcomes.to_csv(outcomes_path, index=False)
    metrics.to_csv(metrics_path, index=False)
    return outcomes_path, metrics_path
