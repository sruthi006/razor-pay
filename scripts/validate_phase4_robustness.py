"""Read-only Phase 4 robustness checks using persisted models only.

No model is fitted or tuned here. Bootstrap resampling reuses each model's
held-out, selected-candidate outcomes at the transaction level.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score, precision_score, recall_score

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.model import (  # noqa: E402
    filter_model_eligible_rows,
    grouped_train_test_split,
    load_and_validate_model_data,
    predict_success_probability,
    select_best_retry_time,
)

THRESHOLDS = (0.30, 0.40, 0.50, 0.60, 0.70)
MODEL_PATHS = {
    "Logistic Regression (original saved)": ROOT / "models" / "smart_retry_logistic_regression.joblib",
    "Random Forest": ROOT / "models" / "smart_retry_best_model.joblib",
}
UNAVAILABLE_MODELS = {
    "HistGradientBoosting": "No fitted model or held-out row-level predictions were saved after the comparison experiment.",
    "Logistic Regression (enhanced experiment)": "No separate fitted model or held-out row-level predictions were saved after the comparison experiment.",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _threshold_metrics(y: pd.Series, probability: pd.Series, threshold: float) -> dict[str, float | int]:
    labels = (probability >= threshold).astype(int)
    return {
        "precision": float(precision_score(y, labels, zero_division=0)),
        "recall": float(recall_score(y, labels, zero_division=0)),
        "f1": float(f1_score(y, labels, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, labels)),
        "positive_predictions": int(labels.sum()),
        "positive_prediction_proportion": float(labels.mean()),
    }


def _selected_outcomes(test_df: pd.DataFrame, probability: pd.Series) -> pd.Series:
    scored = test_df.loc[:, ["transaction_id", "candidate_retry_hours", "retry_success"]].copy()
    scored["predicted_success_probability"] = probability
    selected = select_best_retry_time(scored).sort_values("transaction_id")
    if selected.transaction_id.duplicated().any():
        raise RuntimeError("Selection did not produce one row per transaction.")
    return selected.set_index("transaction_id")["retry_success"].astype(float)


def _bootstrap(selected: dict[str, pd.Series], n_bootstrap: int, seed: int) -> tuple[pd.DataFrame, dict]:
    transaction_ids = selected["Logistic Regression (original saved)"].index
    if not selected["Random Forest"].index.equals(transaction_ids):
        raise RuntimeError("Saved models selected different transaction indices.")
    values = {name: series.to_numpy(dtype=float) for name, series in selected.items()}
    rng = np.random.default_rng(seed)
    samples: list[dict[str, float | int]] = []
    for iteration in range(n_bootstrap):
        indices = rng.integers(0, len(transaction_ids), size=len(transaction_ids))
        lr_rate = float(values["Logistic Regression (original saved)"][indices].mean())
        rf_rate = float(values["Random Forest"][indices].mean())
        samples.append({
            "bootstrap_iteration": iteration + 1,
            "logistic_regression_selected_success_rate": lr_rate,
            "random_forest_selected_success_rate": rf_rate,
            "random_forest_minus_logistic_regression": rf_rate - lr_rate,
        })
    frame = pd.DataFrame(samples)
    point_lr = float(values["Logistic Regression (original saved)"].mean())
    point_rf = float(values["Random Forest"].mean())
    diff = frame["random_forest_minus_logistic_regression"]
    result = {
        "bootstrap_method": "transaction-level resampling with replacement; predictions reused without refitting",
        "n_bootstrap": n_bootstrap,
        "logistic_regression": {"observed_rate": point_lr, "ci_95": [float(frame.iloc[:, 1].quantile(0.025)), float(frame.iloc[:, 1].quantile(0.975))]},
        "random_forest": {"observed_rate": point_rf, "ci_95": [float(frame.iloc[:, 2].quantile(0.025)), float(frame.iloc[:, 2].quantile(0.975))]},
        "random_forest_minus_logistic_regression": {
            "observed_difference": point_rf - point_lr,
            "ci_95": [float(diff.quantile(0.025)), float(diff.quantile(0.975))],
            "bootstrap_probability_greater_than_zero": float((diff > 0).mean()),
        },
        "random_forest_minus_hist_gradient_boosting": {
            "status": "unavailable",
            "reason": UNAVAILABLE_MODELS["HistGradientBoosting"],
        },
    }
    return frame, result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run no-retraining Phase 4 robustness validation.")
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "raw" / "final_prototype_100k_corrected.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "evaluation")
    parser.add_argument("--n-bootstrap", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    source_hash_before = _sha256(args.input)
    source, warnings = load_and_validate_model_data(args.input)
    _, test_df = grouped_train_test_split(filter_model_eligible_rows(source), random_state=42)
    thresholds: list[dict] = []
    selected: dict[str, pd.Series] = {}
    selection_rows: list[dict] = []

    for name, path in MODEL_PATHS.items():
        if not path.is_file():
            raise FileNotFoundError(f"Required saved model unavailable: {path}")
        model = joblib.load(path)
        probability = predict_success_probability(model, test_df)
        for threshold in THRESHOLDS:
            thresholds.append({"model": name, "status": "available", "threshold": threshold, **_threshold_metrics(test_df.retry_success, probability, threshold)})
        chosen = _selected_outcomes(test_df, probability)
        selected[name] = chosen
        distribution = (
            select_best_retry_time(pd.DataFrame({"transaction_id": test_df.transaction_id, "candidate_retry_hours": test_df.candidate_retry_hours, "predicted_success_probability": probability}))
            .candidate_retry_hours.value_counts().sort_index().to_dict()
        )
        selection_rows.append({"model": name, "status": "available", "selected_candidate_success_rate": float(chosen.mean()), "selected_retry_time_distribution": json.dumps(distribution, sort_keys=True)})

    for name, reason in UNAVAILABLE_MODELS.items():
        for threshold in THRESHOLDS:
            thresholds.append({"model": name, "status": "unavailable", "threshold": threshold, "reason": reason})
        selection_rows.append({"model": name, "status": "unavailable", "reason": reason})

    bootstrap_samples, bootstrap_result = _bootstrap(selected, args.n_bootstrap, args.seed)
    source_hash_after = _sha256(args.input)
    if source_hash_before != source_hash_after:
        raise RuntimeError("Authoritative source CSV changed during validation.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    threshold_path = args.output_dir / "phase4_threshold_comparison.csv"
    bootstrap_result_path = args.output_dir / "phase4_bootstrap_results.json"
    bootstrap_samples_path = args.output_dir / "phase4_bootstrap_samples.csv"
    summary_path = args.output_dir / "phase4_robustness_summary.md"
    pd.DataFrame(thresholds).to_csv(threshold_path, index=False)
    bootstrap_samples.to_csv(bootstrap_samples_path, index=False)
    payload = {"source_sha256": source_hash_after, "test_transactions": int(test_df.transaction_id.nunique()), "test_candidate_rows": int(len(test_df)), "selection": selection_rows, "validation_warnings": warnings, **bootstrap_result}
    bootstrap_result_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    ci = bootstrap_result["random_forest_minus_logistic_regression"]["ci_95"]
    conclusion = "directionally positive but statistically uncertain" if ci[0] <= 0 <= ci[1] else "clearly supported"
    summary_path.write_text(
        "# Phase 4 robustness validation\n\n"
        "This pass reused saved models and the same transaction-held-out partition; no model was fitted or tuned.\n\n"
        f"- Held-out transactions: {test_df.transaction_id.nunique()}\n"
        f"- Bootstrap resamples: {args.n_bootstrap}\n"
        f"- Random Forest minus original saved Logistic Regression: {bootstrap_result['random_forest_minus_logistic_regression']['observed_difference']:.4f}; 95% CI [{ci[0]:.4f}, {ci[1]:.4f}]\n"
        f"- Provisional interpretation: **{conclusion}**.\n"
        "- HistGradientBoosting and the enhanced Logistic Regression experiment lack retained fitted pipelines or row-level held-out predictions. Their threshold and bootstrap comparisons are therefore unavailable without retraining, which this validation deliberately does not do.\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
