"""Phase 5: calibrate saved Random Forest probabilities without refitting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.confidence import CalibratedRetryModel, apply_calibrator, confidence_tier  # noqa: E402
from src.model import filter_model_eligible_rows, grouped_train_test_split, load_and_validate_model_data, predict_success_probability, select_best_retry_time  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def ece(y: pd.Series, probability: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    indices = np.clip(np.digitize(probability, bins[1:-1], right=False), 0, n_bins - 1)
    result = 0.0
    for index in range(n_bins):
        mask = indices == index
        if mask.any():
            result += float(mask.mean()) * abs(float(y.iloc[mask].mean()) - float(probability[mask].mean()))
    return result


def metrics(y: pd.Series, probability: np.ndarray) -> dict[str, float]:
    clipped = np.clip(probability, 1e-6, 1 - 1e-6)
    return {
        "brier_score": float(brier_score_loss(y, clipped)),
        "log_loss": float(log_loss(y, clipped)),
        "roc_auc": float(roc_auc_score(y, clipped)),
        "pr_auc": float(average_precision_score(y, clipped)),
        "expected_calibration_error": ece(y.reset_index(drop=True), clipped),
    }


def make_calibrator(method: str):
    if method == "sigmoid":
        return LogisticRegression(C=1.0, solver="lbfgs", max_iter=1_000, random_state=42)
    if method == "isotonic":
        return IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    raise ValueError(f"Unknown calibration method: {method}")


def fit_calibrator(method: str, probability: pd.Series, y: pd.Series):
    calibrator = make_calibrator(method)
    if method == "sigmoid":
        calibrator.fit(np.asarray(probability).reshape(-1, 1), y)
    else:
        calibrator.fit(np.asarray(probability), y)
    return calibrator


def selected_frame(data: pd.DataFrame, raw: np.ndarray, calibrated: np.ndarray) -> pd.DataFrame:
    scored = data.loc[:, ["transaction_id", "candidate_retry_hours", "retry_success"]].copy()
    scored["uncalibrated_probability"] = raw
    scored["calibrated_probability"] = calibrated
    # Select on calibrated values; monotonic calibrators should preserve ranking,
    # while tie-break remains the existing earliest-time rule.
    chooser = scored.rename(columns={"calibrated_probability": "predicted_success_probability"})
    selected = select_best_retry_time(chooser)
    return selected.rename(columns={"predicted_success_probability": "calibrated_probability"})


def reliability_rows(y: pd.Series, probability: np.ndarray, label: str) -> pd.DataFrame:
    observed, predicted = calibration_curve(y, probability, n_bins=10, strategy="uniform")
    return pd.DataFrame({"model_probability": label, "mean_predicted_probability": predicted, "observed_success_rate": observed})


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate saved Phase 4 Random Forest probabilities.")
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "raw" / "final_prototype_100k_corrected.csv")
    parser.add_argument("--base-model", type=Path, default=ROOT / "models" / "smart_retry_best_model.joblib")
    parser.add_argument("--output-model", type=Path, default=ROOT / "models" / "smart_retry_calibrated_model.joblib")
    parser.add_argument("--evaluation-dir", type=Path, default=ROOT / "evaluation")
    args = parser.parse_args()

    before_hash = sha256(args.input)
    source, warnings = load_and_validate_model_data(args.input)
    train_side, outer_test = grouped_train_test_split(filter_model_eligible_rows(source), random_state=42)
    # Dedicated, transaction-grouped calibration fit/validation split; outer test is never used here.
    splitter = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=2026)
    calibration_fit_idx, calibration_validation_idx = next(
        splitter.split(train_side, train_side.retry_success, groups=train_side.transaction_id)
    )
    calibration_fit = train_side.iloc[calibration_fit_idx].copy()
    calibration_validation = train_side.iloc[calibration_validation_idx].copy()
    if set(calibration_fit.transaction_id) & set(calibration_validation.transaction_id):
        raise RuntimeError("Transaction leakage inside calibration split.")
    if set(train_side.transaction_id) & set(outer_test.transaction_id):
        raise RuntimeError("Outer held-out test transactions leaked into training side.")

    base_model = joblib.load(args.base_model)
    fit_raw = predict_success_probability(base_model, calibration_fit)
    validation_raw = predict_success_probability(base_model, calibration_validation)
    candidates: list[dict] = []
    candidates.append({"method": "uncalibrated", "calibrator": None, "validation_probability": validation_raw.to_numpy()})
    for method in ("sigmoid", "isotonic"):
        calibrator = fit_calibrator(method, fit_raw, calibration_fit.retry_success)
        candidates.append({"method": method, "calibrator": calibrator, "validation_probability": apply_calibrator(calibrator, validation_raw)})

    comparison = []
    for candidate in candidates:
        comparison.append({"method": candidate["method"], **metrics(calibration_validation.retry_success, candidate["validation_probability"])})
    comparison_frame = pd.DataFrame(comparison).sort_values(["brier_score", "log_loss", "expected_calibration_error"]).reset_index(drop=True)
    selected_method = str(comparison_frame.iloc[0].method)

    # Refit only the selected calibrator on all original training-side transactions.
    # The persisted RF itself is never fitted or changed.
    train_raw = predict_success_probability(base_model, train_side)
    selected_calibrator = None if selected_method == "uncalibrated" else fit_calibrator(selected_method, train_raw, train_side.retry_success)
    test_raw = predict_success_probability(base_model, outer_test).to_numpy()
    test_calibrated = test_raw if selected_calibrator is None else apply_calibrator(selected_calibrator, test_raw)
    test_uncalibrated_metrics = metrics(outer_test.retry_success, test_raw)
    test_calibrated_metrics = metrics(outer_test.retry_success, test_calibrated)

    # Tiers are equal-support probability bands whose boundaries are derived from
    # calibration-validation predicted-probability terciles, not hand-picked.
    validation_selected = selected_frame(calibration_validation, validation_raw.to_numpy(), candidates[[c["method"] for c in candidates].index(selected_method)]["validation_probability"])
    low_cut, high_cut = np.quantile(validation_selected.calibrated_probability, [1 / 3, 2 / 3])
    wrapper = CalibratedRetryModel(
        base_model=base_model,
        calibrator=selected_calibrator if selected_calibrator is not None else make_calibrator("sigmoid").fit(np.array([[0.0], [1.0]]), np.array([0, 1])),
        calibration_method=selected_method,
        low_confidence_cut=float(low_cut),
        high_confidence_cut=float(high_cut),
    )
    # For uncalibrated selection, do not use the dummy calibrator; selected method
    # will normally be sigmoid/isotonic, but keep the result correct if not.
    if selected_method == "uncalibrated":
        test_selected = selected_frame(outer_test, test_raw, test_raw)
    else:
        test_selected = wrapper.select_retry_time(outer_test)
    test_selected["confidence_tier"] = confidence_tier(test_selected.calibrated_probability, float(low_cut), float(high_cut))
    # Ensure both fields are retained under explicit names in artifact.
    if "uncalibrated_probability" not in test_selected:
        test_selected["uncalibrated_probability"] = np.nan
    tier_summary = test_selected.groupby("confidence_tier", observed=False).agg(
        transactions=("transaction_id", "count"),
        mean_calibrated_probability=("calibrated_probability", "mean"),
        observed_success_rate=("retry_success", "mean"),
    ).reset_index()

    reliability = pd.concat([
        reliability_rows(outer_test.retry_success, test_raw, "uncalibrated"),
        reliability_rows(outer_test.retry_success, test_calibrated, f"calibrated_{selected_method}"),
    ], ignore_index=True)
    args.evaluation_dir.mkdir(parents=True, exist_ok=True)
    comparison_path = args.evaluation_dir / "phase5_calibration_method_comparison.csv"
    metrics_path = args.evaluation_dir / "phase5_calibration_metrics.json"
    selected_path = args.evaluation_dir / "phase5_selected_retry_predictions.csv"
    tiers_path = args.evaluation_dir / "phase5_confidence_tiers.csv"
    reliability_path = args.evaluation_dir / "phase5_reliability_curve.csv"
    comparison_frame.to_csv(comparison_path, index=False)
    test_selected.to_csv(selected_path, index=False)
    tier_summary.to_csv(tiers_path, index=False)
    reliability.to_csv(reliability_path, index=False)
    joblib.dump(wrapper, args.output_model)
    after_hash = sha256(args.input)
    if before_hash != after_hash:
        raise RuntimeError("Authoritative source CSV changed during calibration.")
    result = {
        "selected_method": selected_method,
        "selection_rule": "lowest transaction-grouped calibration-validation Brier score; log loss and ECE tie-breaks",
        "source_sha256": after_hash,
        "outer_test_transactions": int(outer_test.transaction_id.nunique()),
        "outer_test_candidate_rows": int(len(outer_test)),
        "calibration_fit_transactions": int(calibration_fit.transaction_id.nunique()),
        "calibration_validation_transactions": int(calibration_validation.transaction_id.nunique()),
        "outer_test_uncalibrated_metrics": test_uncalibrated_metrics,
        "outer_test_calibrated_metrics": test_calibrated_metrics,
        "selected_retry": {
            "mean_uncalibrated_probability": float(test_selected.uncalibrated_probability.mean()),
            "mean_calibrated_probability": float(test_selected.calibrated_probability.mean()),
            "observed_success_rate": float(test_selected.retry_success.mean()),
            "tier_boundaries": {"low_to_medium": float(low_cut), "medium_to_high": float(high_cut)},
        },
        "validation_warnings": warnings + [
            "The persisted Random Forest was trained on all training-side transactions, so calibration examples are not out-of-sample for the base model. No base-model out-of-fold probabilities were retained; this limitation may make calibration quality optimistic."
        ],
    }
    metrics_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
