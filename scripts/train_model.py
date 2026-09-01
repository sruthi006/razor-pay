"""Compare Phase 4 models without touching the authoritative source CSV.

The prior Logistic Regression artifact remains intact. This script creates
separate comparison outputs and saves only the winning experiment pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.model import (  # noqa: E402
    EXCLUDED_COLUMNS,
    FEATURE_COLUMNS,
    build_feature_frame,
    build_hist_gradient_pipeline,
    build_random_forest_pipeline,
    evaluate_model,
    filter_model_eligible_rows,
    grouped_train_test_split,
    load_and_validate_model_data,
    save_model,
    train,
    tune_with_group_cv,
)

DEFAULT_INPUT = ROOT / "data" / "raw" / "final_prototype_100k_corrected.csv"
DEFAULT_MODEL = ROOT / "models" / "smart_retry_best_model.joblib"
DEFAULT_EVALUATION = ROOT / "evaluation"

HGB_CANDIDATES = [
    {"learning_rate": 0.05, "max_leaf_nodes": 15, "min_samples_leaf": 30, "l2_regularization": 0.5},
    {"learning_rate": 0.08, "max_leaf_nodes": 31, "min_samples_leaf": 40, "l2_regularization": 1.0},
    {"learning_rate": 0.10, "max_leaf_nodes": 31, "min_samples_leaf": 60, "l2_regularization": 2.0},
]
RF_CANDIDATES = [
    {"n_estimators": 120, "max_depth": 16, "min_samples_leaf": 5, "max_features": "sqrt", "class_weight": None},
    {"n_estimators": 120, "max_depth": 20, "min_samples_leaf": 12, "max_features": "sqrt", "class_weight": "balanced_subsample"},
]


def _fit_and_measure(name: str, model, test_df: pd.DataFrame, tuning_auc: float | None, parameters: dict) -> tuple[dict, object, pd.DataFrame, pd.DataFrame]:
    metrics, by_time, confusion = evaluate_model(model, test_df)
    row = {"model": name, **metrics, "train_cv_roc_auc": tuning_auc, "parameters": json.dumps(parameters, sort_keys=True)}
    return row, model, by_time, confusion


def main() -> None:
    parser = argparse.ArgumentParser(description="Run leakage-safe Phase 4 model comparison.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--evaluation-dir", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    source, warnings = load_and_validate_model_data(args.input)
    eligible = filter_model_eligible_rows(source)
    train_df, test_df = grouped_train_test_split(eligible, random_state=args.random_state)
    majority_accuracy = float(1.0 - test_df["retry_success"].mean())

    candidates: list[tuple[dict, object, pd.DataFrame, pd.DataFrame]] = []
    logistic = train(train_df)
    candidates.append(_fit_and_measure("Logistic Regression", logistic, test_df, None, {"solver": "lbfgs", "max_iter": 1000}))

    hgb_params, hgb_cv_auc = tune_with_group_cv(build_hist_gradient_pipeline, HGB_CANDIDATES, train_df)
    hgb = build_hist_gradient_pipeline(**hgb_params)
    hgb.fit(build_feature_frame(train_df), train_df["retry_success"])
    candidates.append(_fit_and_measure("HistGradientBoosting", hgb, test_df, hgb_cv_auc, hgb_params))

    rf_params, rf_cv_auc = tune_with_group_cv(build_random_forest_pipeline, RF_CANDIDATES, train_df)
    random_forest = build_random_forest_pipeline(**rf_params)
    random_forest.fit(build_feature_frame(train_df), train_df["retry_success"])
    candidates.append(_fit_and_measure("Random Forest", random_forest, test_df, rf_cv_auc, rf_params))

    comparison = pd.DataFrame([row for row, _, _, _ in candidates])
    comparison["majority_class_baseline_accuracy"] = majority_accuracy
    # Select after final hold-out evaluation using discrimination and the actual
    # downstream selection task, without re-tuning on the test partition.
    comparison["selection_score"] = 0.60 * comparison["roc_auc"] + 0.40 * comparison["top_choice_observed_success_rate"]
    comparison = comparison.sort_values(["selection_score", "roc_auc"], ascending=False).reset_index(drop=True)
    winner_name = str(comparison.iloc[0]["model"])
    winner_idx = next(i for i, (row, *_rest) in enumerate(candidates) if row["model"] == winner_name)
    winner_row, winner_model, winner_by_time, winner_confusion = candidates[winner_idx]

    args.evaluation_dir.mkdir(parents=True, exist_ok=True)
    comparison_path = args.evaluation_dir / "model_comparison.csv"
    best_metrics_path = args.evaluation_dir / "best_model_metrics.json"
    best_by_time_path = args.evaluation_dir / "best_model_metrics_by_candidate_time.csv"
    best_confusion_path = args.evaluation_dir / "best_model_confusion_matrix.csv"
    comparison.to_csv(comparison_path, index=False)
    winner_by_time.to_csv(best_by_time_path, index=False)
    winner_confusion.to_csv(best_confusion_path)
    best_payload = {
        "best_model": winner_name,
        "selection_basis": "0.60 * held-out ROC-AUC + 0.40 * held-out selected-candidate success rate; hyperparameters tuned only by train grouped CV",
        "majority_class_baseline_accuracy": majority_accuracy,
        "features": list(FEATURE_COLUMNS),
        "engineered_features": [
            "decline_reason × candidate_retry_hours",
            "payment_method × candidate_retry_hours",
            "log(amount_inr)", "amount_band",
            "customer_previous_success_rate / (1 + customer_previous_failure_count)",
            "cyclic failure hour, day of week, and candidate-derived retry hour",
        ],
        "excluded_columns": list(EXCLUDED_COLUMNS),
        "split": {"method": "StratifiedGroupKFold", "n_splits": 5, "held_out_fold": 1, "group_column": "transaction_id", "train_transactions": int(train_df.transaction_id.nunique()), "test_transactions": int(test_df.transaction_id.nunique()), "transaction_overlap": 0},
        "best_model_metrics": winner_row,
        "validation_warnings": warnings,
    }
    best_metrics_path.write_text(json.dumps(best_payload, indent=2, sort_keys=True), encoding="utf-8")
    model_path = save_model(winner_model, args.model_path)

    print("=== Phase 4 model comparison ===")
    print(comparison.drop(columns=["parameters"]).to_string(index=False))
    print(f"\nBest model: {winner_name}")
    print(f"Majority-class baseline accuracy: {majority_accuracy:.6f}")
    print("\nValidation warnings:")
    print("- none" if not warnings else "\n".join(f"- {warning}" for warning in warnings))
    print(f"\nComparison: {comparison_path}\nBest model: {model_path}\nBest metrics: {best_metrics_path}")


if __name__ == "__main__":
    main()
