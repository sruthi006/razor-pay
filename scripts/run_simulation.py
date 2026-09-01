"""Run Phase 6 fair fixed-schedule vs calibrated Smart Retry simulation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.baseline import load_and_validate_dataset  # noqa: E402
from src.simulation import bootstrap_strategy_difference, breakdown, build_transaction_comparison, strategy_summary  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def amount_band(amount: pd.Series) -> pd.Series:
    return pd.cut(amount, [-np.inf, 1_000, 5_000, 20_000, np.inf], labels=["under_1k", "1k_to_5k", "5k_to_20k", "20k_plus"]).astype(str)


def write_business_summary(path: Path, summary: dict, bootstrap: dict, distribution: pd.DataFrame) -> None:
    rate_ci = bootstrap["incremental_recovery_rate_ci_95"]
    inr_ci = bootstrap["incremental_recovered_inr_ci_95"]
    conclusive = not (rate_ci[0] <= 0 <= rate_ci[1])
    outside = float(distribution.loc[distribution["selection_type"] == "outside_fixed_schedule", "selection_pct"].sum())
    path.write_text(
        "# Phase 6 business-value simulation\n\n"
        "Both policies were applied to the identical SOFT_RETRY transaction population. Smart Retry makes one calibrated model-selected decision; fixed schedule may attempt +24h, +48h, +72h and stops at first success.\n\n"
        f"- Eligible transactions: {summary['eligible_transactions']:,}\n"
        f"- Fixed recovered INR: ₹{summary['fixed_recovered_inr']:,.2f}\n"
        f"- Smart Retry recovered INR: ₹{summary['smart_recovered_inr']:,.2f}\n"
        f"- Incremental INR: ₹{summary['incremental_recovered_inr']:,.2f}; 95% bootstrap CI [₹{inr_ci[0]:,.2f}, ₹{inr_ci[1]:,.2f}]\n"
        f"- Incremental recovery rate: {summary['incremental_recovery_rate']:.2%}; 95% bootstrap CI [{rate_ci[0]:.2%}, {rate_ci[1]:.2%}]\n"
        f"- Smart Retry chose a time outside +24/+48/+72h for {outside:.2%} of eligible transactions.\n\n"
        "## Interpretation\n\n"
        + ("The bootstrap interval excludes zero, so this simulated incremental effect is statistically supported conditional on this dataset and policy setup.\n" if conclusive else "The bootstrap interval crosses zero, so the point estimate is directionally positive but statistically uncertain.\n")
        + "\n## Limitations\n\n"
        "- This is synthetic data; it is not evidence of production Razorpay outcomes.\n"
        "- The saved scorer was trained on a subset of the same full population used here, so this whole-population business simulation is not a fully out-of-sample policy estimate.\n"
        "- Calibration improved global reliability but the High confidence tier remained overconfident in Phase 5.\n"
        "- The comparison is one Smart Retry attempt versus a three-opportunity fixed schedule; it is a policy prototype, not a live retry policy.\n"
        "- Phase 4 did not establish conclusive Random Forest superiority over Logistic Regression.\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 6 Business-Value Simulation.")
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "raw" / "final_prototype_100k_corrected.csv")
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "smart_retry_calibrated_model.joblib")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "evaluation")
    parser.add_argument("--bootstrap-resamples", type=int, default=5_000)
    args = parser.parse_args()
    before_hash = sha256(args.input)
    source, warnings = load_and_validate_dataset(args.input)
    model = joblib.load(args.model)
    comparison = build_transaction_comparison(source, model)
    if len(comparison) != 7_471:
        warnings.append(f"Expected 7,471 eligible transactions from Phase 3, found {len(comparison):,}.")
    phase3_summary = ROOT / "evaluation" / "fixed_schedule_baseline_summary.csv"
    summary = strategy_summary(comparison)
    if phase3_summary.is_file():
        phase3 = pd.read_csv(phase3_summary).set_index("metric")["value"]
        if not np.isclose(summary["fixed_recovered_inr"], float(phase3["recovered_inr"])) or summary["fixed_recovered_transactions"] != int(phase3["recovered_transactions"]):
            raise ValueError("Reconstructed eligible baseline does not reconcile with validated Phase 3 totals.")
    bootstrap = bootstrap_strategy_difference(comparison, args.bootstrap_resamples)
    comparison["amount_band"] = amount_band(comparison.amount_inr)
    breakdown(comparison, "decline_reason").to_csv(args.output_dir / "phase6_breakdown_by_decline_reason.csv", index=False)
    breakdown(comparison, "decline_bucket").to_csv(args.output_dir / "phase6_breakdown_by_decline_bucket.csv", index=False)
    breakdown(comparison, "payment_method").to_csv(args.output_dir / "phase6_breakdown_by_payment_method.csv", index=False)
    breakdown(comparison, "amount_band").to_csv(args.output_dir / "phase6_breakdown_by_amount_band.csv", index=False)
    breakdown(comparison, "smart_retry_confidence").to_csv(args.output_dir / "phase6_breakdown_by_confidence.csv", index=False)
    distribution = breakdown(comparison, "smart_retry_selected_hours").rename(columns={"smart_retry_selected_hours": "selected_retry_hours"})
    distribution["selection_type"] = np.where(distribution.selected_retry_hours.isin([24.0, 48.0, 72.0]), "fixed_schedule_time", "outside_fixed_schedule")
    distribution["selection_pct"] = distribution.eligible_transactions / len(comparison)
    distribution.to_csv(args.output_dir / "phase6_retry_time_distribution.csv", index=False)
    required_columns = [
        "transaction_id", "amount_inr", "decline_reason", "payment_method", "baseline_selected_schedule",
        "baseline_success", "baseline_recovered_inr", "smart_retry_selected_hours", "smart_retry_probability",
        "smart_retry_confidence", "smart_retry_success", "smart_retry_recovered_inr", "incremental_recovery_inr",
    ]
    comparison.loc[:, required_columns].to_csv(args.output_dir / "phase6_transaction_comparison.csv", index=False)
    inside = comparison.smart_retry_selected_hours.isin([24.0, 48.0, 72.0])
    diagnostics = {
        "pct_recommendations_at_24_48_72": float(inside.mean()),
        "pct_recommendations_outside_24_48_72": float((~inside).mean()),
        "recovery_rate_inside_fixed_schedule_times": float(comparison.loc[inside, "smart_retry_success"].mean()),
        "recovery_rate_outside_fixed_schedule_times": float(comparison.loc[~inside, "smart_retry_success"].mean()),
    }
    after_hash = sha256(args.input)
    if before_hash != after_hash:
        raise RuntimeError("Authoritative source CSV changed during Phase 6 simulation.")
    payload = {"source_sha256": after_hash, "summary": summary, "bootstrap": bootstrap, "selection_diagnostics": diagnostics, "validation_warnings": warnings}
    (args.output_dir / "phase6_summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    (args.output_dir / "phase6_bootstrap_results.json").write_text(json.dumps(bootstrap, indent=2, sort_keys=True), encoding="utf-8")
    write_business_summary(args.output_dir / "phase6_business_summary.md", summary, bootstrap, distribution)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
