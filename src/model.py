"""Phase 4 interpretable model for retry-success probability.

The pipeline is intentionally limited to information known when a candidate
retry is considered. It trains only on ``SOFT_RETRY`` rows, matching the
business rules, and can be reused by Phase 5 and Phase 6.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, average_precision_score, balanced_accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from src.decline_codes import RetryCategory, retry_category_for

TARGET_COLUMN = "retry_success"
GROUP_COLUMN = "transaction_id"
RAW_CATEGORICAL_FEATURES: tuple[str, ...] = ("decline_reason", "payment_method")
# This interaction lets an interpretable linear classifier represent the
# documented reason-specific timing curves without exposing any hidden DGP
# state. It is derived solely from two permitted scoring-time inputs.
ENGINEERED_CATEGORICAL_FEATURES: tuple[str, ...] = (
    "decline_reason_retry_time", "payment_method_retry_time", "amount_band",
)
CATEGORICAL_FEATURES: tuple[str, ...] = RAW_CATEGORICAL_FEATURES + ENGINEERED_CATEGORICAL_FEATURES
RAW_NUMERIC_FEATURES: tuple[str, ...] = (
    "amount_inr", "hour_of_day", "day_of_month", "day_of_week",
    "candidate_retry_hours", "customer_previous_success_rate",
    "customer_previous_failure_count", "days_since_last_successful_payment",
)
NUMERIC_FEATURES: tuple[str, ...] = RAW_NUMERIC_FEATURES + (
    "log_amount_inr", "customer_reliability_score",
    "failure_hour_sin", "failure_hour_cos", "day_of_week_sin", "day_of_week_cos",
    "retry_hour_sin", "retry_hour_cos",
)
FEATURE_COLUMNS: tuple[str, ...] = RAW_CATEGORICAL_FEATURES + RAW_NUMERIC_FEATURES

# Not model inputs. See docs/data_schema.md for the project leakage policy.
EXCLUDED_COLUMNS: tuple[str, ...] = (
    "retry_success", "transaction_id", "customer_id", "decline_bucket",
    "failure_timestamp", "hours_since_failure", "retry_attempt_number",
)
REQUIRED_COLUMNS = frozenset({GROUP_COLUMN, TARGET_COLUMN, "decline_bucket", *FEATURE_COLUMNS})


def _known_reason(reason: str) -> bool:
    try:
        retry_category_for(reason)
    except KeyError:
        return False
    return True


def load_and_validate_model_data(path: str | Path) -> tuple[pd.DataFrame, list[str]]:
    """Read and validate source data without changing the authoritative CSV."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Model input dataset not found: {path}")
    df = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"Dataset is missing model-required columns: {missing}")
    if df.empty:
        raise ValueError("Dataset is empty.")
    if df[list(REQUIRED_COLUMNS)].isna().any().any():
        nulls = df[list(REQUIRED_COLUMNS)].columns[df[list(REQUIRED_COLUMNS)].isna().any()]
        raise ValueError(f"Model-required columns contain nulls: {list(nulls)}")
    if not df[TARGET_COLUMN].isin([0, 1]).all():
        raise ValueError("retry_success must contain only 0 and 1.")
    if df.duplicated([GROUP_COLUMN, "candidate_retry_hours"]).any():
        raise ValueError("Duplicate transaction_id/candidate_retry_hours rows found.")
    unknown = [value for value in df["decline_reason"].unique() if not _known_reason(value)]
    if unknown:
        raise ValueError(f"Unknown decline reason(s): {sorted(unknown)}")
    expected_bucket = df["decline_reason"].map(lambda value: retry_category_for(value).value)
    if not (df["decline_bucket"] == expected_bucket).all():
        raise ValueError("decline_bucket conflicts with the Phase 1 catalog.")
    warnings = []
    if "hours_since_failure" not in df.columns:
        warnings.append("Source has no hours_since_failure; candidate_retry_hours is the sole candidate-time feature.")
    return df, warnings


def filter_model_eligible_rows(data: pd.DataFrame) -> pd.DataFrame:
    """Return only rows the smart-retry model is permitted to score."""
    eligible = data.loc[data["decline_bucket"] == RetryCategory.SOFT_RETRY.value].copy()
    if eligible.empty:
        raise ValueError("No SOFT_RETRY rows available for model training.")
    return eligible


def build_feature_frame(data: pd.DataFrame) -> pd.DataFrame:
    """Create only legitimate, decision-time model inputs."""
    frame = data.loc[:, list(FEATURE_COLUMNS)].copy()
    frame["decline_reason_retry_time"] = (
        frame["decline_reason"].astype(str)
        + "__"
        + frame["candidate_retry_hours"].astype(str)
    )
    frame["payment_method_retry_time"] = frame["payment_method"].astype(str) + "__" + frame["candidate_retry_hours"].astype(str)
    frame["amount_band"] = pd.cut(frame["amount_inr"], [-np.inf, 1_000, 5_000, 20_000, np.inf], labels=["under_1k", "1k_to_5k", "5k_to_20k", "20k_plus"]).astype(str)
    frame["log_amount_inr"] = np.log1p(frame["amount_inr"].astype(float))
    frame["customer_reliability_score"] = frame["customer_previous_success_rate"].astype(float) / (1.0 + frame["customer_previous_failure_count"].astype(float))
    hour_angle = 2.0 * np.pi * frame["hour_of_day"].astype(float) / 24.0
    day_angle = 2.0 * np.pi * frame["day_of_week"].astype(float) / 7.0
    retry_angle = 2.0 * np.pi * ((frame["hour_of_day"].astype(float) + frame["candidate_retry_hours"].astype(float)) % 24.0) / 24.0
    frame["failure_hour_sin"], frame["failure_hour_cos"] = np.sin(hour_angle), np.cos(hour_angle)
    frame["day_of_week_sin"], frame["day_of_week_cos"] = np.sin(day_angle), np.cos(day_angle)
    frame["retry_hour_sin"], frame["retry_hour_cos"] = np.sin(retry_angle), np.cos(retry_angle)
    return frame


def build_pipeline() -> Pipeline:
    """Create one encoded/scaled Logistic Regression scoring pipeline."""
    preprocessing = ColumnTransformer(
        [
            ("categorical", OneHotEncoder(handle_unknown="ignore"), list(CATEGORICAL_FEATURES)),
            ("numeric", StandardScaler(), list(NUMERIC_FEATURES)),
        ],
        remainder="drop",
    )
    classifier = LogisticRegression(max_iter=1_000, solver="lbfgs", random_state=42)
    return Pipeline([("preprocessing", preprocessing), ("classifier", classifier)])


def grouped_train_test_split(data: pd.DataFrame, random_state: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use a transaction-grouped 80/20 split; candidate rows never cross it."""
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=random_state)
    train_idx, test_idx = next(splitter.split(data, data[TARGET_COLUMN], groups=data[GROUP_COLUMN]))
    train_df, test_df = data.iloc[train_idx].copy(), data.iloc[test_idx].copy()
    if set(train_df[GROUP_COLUMN]) & set(test_df[GROUP_COLUMN]):
        raise RuntimeError("Transaction leakage: train/test groups overlap.")
    return train_df, test_df


def train(train_df: pd.DataFrame) -> Pipeline:
    """Fit the combined preprocessing and Logistic Regression pipeline."""
    model = build_pipeline()
    model.fit(build_feature_frame(train_df), train_df[TARGET_COLUMN])
    return model


def predict_success_probability(model: Pipeline, features: pd.DataFrame) -> pd.Series:
    """Predict P(retry_success=1) for candidate rows."""
    missing = sorted(set(FEATURE_COLUMNS) - set(features.columns))
    if missing:
        raise ValueError(f"Missing scoring features: {missing}")
    probabilities = model.predict_proba(build_feature_frame(features))[:, 1]
    return pd.Series(probabilities, index=features.index, name="predicted_success_probability")


def select_best_retry_time(scored_candidates: pd.DataFrame) -> pd.DataFrame:
    """Select max probability per transaction; earliest retry wins a tie."""
    required = {GROUP_COLUMN, "candidate_retry_hours", "predicted_success_probability"}
    missing = sorted(required - set(scored_candidates.columns))
    if missing:
        raise ValueError(f"Cannot choose retry time; missing columns: {missing}")
    ordered = scored_candidates.sort_values(
        [GROUP_COLUMN, "predicted_success_probability", "candidate_retry_hours"],
        ascending=[True, False, True],
    )
    return ordered.groupby(GROUP_COLUMN, as_index=False).first()


def _classification_metrics(y_true: pd.Series, probabilities: pd.Series) -> dict[str, float | None]:
    predictions = (probabilities >= 0.5).astype(int)
    values: dict[str, float | None] = {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predictions)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "roc_auc": None,
        "pr_auc": None,
    }
    if y_true.nunique() == 2:
        values["roc_auc"] = float(roc_auc_score(y_true, probabilities))
        values["pr_auc"] = float(average_precision_score(y_true, probabilities))
    return values


def evaluate_model(model: Pipeline, test_df: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """Evaluate classification and test-only top-candidate decision quality."""
    probabilities = predict_success_probability(model, test_df)
    metrics = _classification_metrics(test_df[TARGET_COLUMN], probabilities)
    predicted_labels = (probabilities >= 0.5).astype(int)
    matrix = confusion_matrix(test_df[TARGET_COLUMN], predicted_labels, labels=[0, 1])
    confusion = pd.DataFrame(matrix, index=["actual_0", "actual_1"], columns=["predicted_0", "predicted_1"])

    evaluated = test_df.loc[:, [GROUP_COLUMN, "candidate_retry_hours", TARGET_COLUMN]].copy()
    evaluated["predicted_success_probability"] = probabilities
    per_time: list[dict[str, float | None]] = []
    for hours, rows in evaluated.groupby("candidate_retry_hours", sort=True):
        item: dict[str, float | None] = {
            "candidate_retry_hours": float(hours), "rows": float(len(rows)),
            "observed_success_rate": float(rows[TARGET_COLUMN].mean()),
        }
        item.update(_classification_metrics(rows[TARGET_COLUMN], rows["predicted_success_probability"]))
        per_time.append(item)

    selected = select_best_retry_time(evaluated)
    metrics.update(
        {
            "test_transactions": int(test_df[GROUP_COLUMN].nunique()),
            "test_candidate_rows": int(len(test_df)),
            # Evaluation-only use of labels; never fed to the model.
            "top_choice_observed_success_rate": float(selected[TARGET_COLUMN].mean()),
            "top_choice_mean_predicted_probability": float(selected["predicted_success_probability"].mean()),
        }
    )
    return metrics, pd.DataFrame(per_time), confusion


def save_model(model: Pipeline, path: str | Path) -> Path:
    """Persist the pipeline, including preprocessing, in models/."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    return path


def save_evaluation_artifacts(metrics: dict[str, Any], by_time: pd.DataFrame, confusion: pd.DataFrame, output_dir: str | Path) -> tuple[Path, Path, Path]:
    """Save model metrics, candidate-time metrics and a confusion matrix."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "logistic_regression_metrics.json"
    by_time_path = output_dir / "logistic_regression_metrics_by_candidate_time.csv"
    confusion_path = output_dir / "logistic_regression_confusion_matrix.csv"
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    by_time.to_csv(by_time_path, index=False)
    confusion.to_csv(confusion_path)
    return metrics_path, by_time_path, confusion_path


def build_hist_gradient_pipeline(**params: Any) -> Pipeline:
    """Dense ordinal preprocessing required by HistGradientBoostingClassifier."""
    preprocessing = ColumnTransformer([
        ("categorical", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), list(CATEGORICAL_FEATURES)),
        ("numeric", SimpleImputer(strategy="median"), list(NUMERIC_FEATURES)),
    ], remainder="drop")
    classifier = HistGradientBoostingClassifier(
        random_state=42,
        categorical_features=list(range(len(CATEGORICAL_FEATURES))),
        **params,
    )
    return Pipeline([("preprocessing", preprocessing), ("classifier", classifier)])


def build_random_forest_pipeline(**params: Any) -> Pipeline:
    """One-hot preprocessing plus Random Forest for non-linear interactions."""
    preprocessing = ColumnTransformer([
        ("categorical", OneHotEncoder(handle_unknown="ignore"), list(CATEGORICAL_FEATURES)),
        ("numeric", SimpleImputer(strategy="median"), list(NUMERIC_FEATURES)),
    ], remainder="drop")
    return Pipeline([("preprocessing", preprocessing), ("classifier", RandomForestClassifier(random_state=42, n_jobs=-1, **params))])


def tune_with_group_cv(builder: Any, parameter_candidates: list[dict[str, Any]], train_df: pd.DataFrame, random_state: int = 17) -> tuple[dict[str, Any], float]:
    """Choose parameters by train-only grouped 3-fold CV ROC-AUC."""
    splitter = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=random_state)
    best_params: dict[str, Any] | None = None
    best_score = -np.inf
    for params in parameter_candidates:
        scores: list[float] = []
        for fit_idx, valid_idx in splitter.split(train_df, train_df[TARGET_COLUMN], train_df[GROUP_COLUMN]):
            fit_df, valid_df = train_df.iloc[fit_idx], train_df.iloc[valid_idx]
            candidate = builder(**params)
            candidate.fit(build_feature_frame(fit_df), fit_df[TARGET_COLUMN])
            probability = candidate.predict_proba(build_feature_frame(valid_df))[:, 1]
            scores.append(float(roc_auc_score(valid_df[TARGET_COLUMN], probability)))
        score = float(np.mean(scores))
        if score > best_score:
            best_params, best_score = params, score
    if best_params is None:
        raise RuntimeError("No parameters evaluated during grouped CV.")
    return best_params, best_score
