"""Read validated Phase 5/6 artifacts for dashboard-facing endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.simulation import breakdown as simulation_breakdown
from src.simulation import strategy_summary


class DashboardService:
    def __init__(self, evaluation_dir: Path) -> None:
        self.evaluation_dir = evaluation_dir
        self._active_dataset: dict[str, Any] | None = None

    @staticmethod
    def _coerce_bool(value: Any) -> bool | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"1", "true", "yes", "y"}:
                return True
            if cleaned in {"0", "false", "no", "n"}:
                return False
            return None
        if isinstance(value, (int, np.integer, bool, np.bool_)):
            return bool(value)
        if isinstance(value, (float, np.floating)):
            return bool(int(value)) if not pd.isna(value) else None
        return None

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            numeric = pd.to_numeric(value, errors="coerce")
            if pd.isna(numeric):
                return None
            return float(numeric)
        except Exception:
            return None

    @staticmethod
    def _wide_observed_outcomes_frame(rows: pd.DataFrame) -> pd.DataFrame | None:
        """Support the synthetic evaluation CSV format used for uploaded observed outcomes."""
        required = {
            "transaction_id",
            "amount_inr",
            "decline_reason",
            "payment_method",
            "fixed_retry_hours",
            "smart_retry_hours",
            "fixed_retry_success",
            "smart_retry_success",
            "fixed_recovered_inr",
            "smart_recovered_inr",
        }
        missing = sorted(required - set(rows.columns))
        if missing:
            return None

        frame = rows.copy()
        if frame.empty:
            return None

        numeric_columns = ["amount_inr", "fixed_retry_hours", "smart_retry_hours", "fixed_recovered_inr", "smart_recovered_inr"]
        for column in numeric_columns:
            converted = pd.to_numeric(frame[column], errors="coerce")
            if converted.isna().all():
                return None
            frame[column] = converted

        fixed_success = frame["fixed_retry_success"].map(DashboardService._coerce_bool)
        smart_success = frame["smart_retry_success"].map(DashboardService._coerce_bool)
        if fixed_success.isna().all() or smart_success.isna().all():
            return None

        comparison = pd.DataFrame({
            "transaction_id": frame["transaction_id"].astype(str),
            "amount_inr": frame["amount_inr"].astype(float),
            "decline_reason": frame["decline_reason"].astype(str),
            "payment_method": frame["payment_method"].astype(str),
            "baseline_selected_schedule": frame["fixed_retry_hours"].astype(float),
            "baseline_success": fixed_success.fillna(False).astype(bool),
            "baseline_recovered_inr": np.where(fixed_success.fillna(False).astype(bool), frame["fixed_recovered_inr"].fillna(0.0).astype(float), 0.0),
            "smart_retry_selected_hours": frame["smart_retry_hours"].astype(float),
            "smart_retry_probability": np.nan,
            "smart_retry_confidence": np.nan,
            "smart_retry_success": smart_success.fillna(False).astype(bool),
            "smart_retry_recovered_inr": np.where(smart_success.fillna(False).astype(bool), frame["smart_recovered_inr"].fillna(0.0).astype(float), 0.0),
        })
        comparison["incremental_recovery_inr"] = comparison["smart_retry_recovered_inr"] - comparison["baseline_recovered_inr"]
        comparison["baseline_success"] = comparison["baseline_success"].astype(bool)
        comparison["smart_retry_success"] = comparison["smart_retry_success"].astype(bool)
        return comparison.sort_values("transaction_id").reset_index(drop=True)

    @staticmethod
    def _comparison_from_uploaded_rows(rows: pd.DataFrame, model: Any) -> pd.DataFrame | None:
        """Accept both the legacy candidate-grid schema and the wide evaluation CSV format."""
        from src.baseline import REQUIRED_COLUMNS

        if REQUIRED_COLUMNS.issubset(rows.columns):
            try:
                from src.simulation import build_transaction_comparison
                return build_transaction_comparison(rows, model)
            except (KeyError, TypeError, ValueError):
                return None

        wide = DashboardService._wide_observed_outcomes_frame(rows)
        if wide is not None:
            return wide
        return None

    def activate_dataset(
        self,
        source: str,
        raw_rows: pd.DataFrame,
        inference: dict[str, Any],
        comparison: pd.DataFrame | None = None,
    ) -> None:
        """Keep the most recently selected dataset in the API process.

        ``comparison`` is provided only when the uploaded data contains valid
        observed outcomes for a fair fixed-vs-smart policy evaluation. Raw
        inference-only uploads deliberately do not receive fabricated outcome
        metrics.
        """
        transactions = self._inference_transactions(raw_rows, inference.get("results", []))
        dataset_id = f"{source}:{abs(hash(raw_rows.to_csv(index=False))) % 1000000}"
        dataset_label = "Selected uploaded CSV" if source == "upload" else "Validated demo evaluation dataset"
        merged_comparison = comparison.copy() if comparison is not None else None
        if merged_comparison is not None and not merged_comparison.empty:
            context = transactions.loc[:, ["transaction_id", "smart_retry_selected_hours", "smart_retry_probability", "smart_retry_confidence"]].drop_duplicates(subset="transaction_id")
            if not context.empty:
                merged_comparison = merged_comparison.merge(
                    context,
                    on="transaction_id",
                    how="left",
                    validate="one_to_one",
                )
                merged_comparison["smart_retry_selected_hours"] = merged_comparison["smart_retry_selected_hours_y"].combine_first(merged_comparison["smart_retry_selected_hours_x"])
                merged_comparison["smart_retry_probability"] = merged_comparison["smart_retry_probability_y"].combine_first(merged_comparison["smart_retry_probability_x"])
                merged_comparison["smart_retry_confidence"] = merged_comparison["smart_retry_confidence_y"].combine_first(merged_comparison["smart_retry_confidence_x"])
                merged_comparison = merged_comparison.drop(columns=["smart_retry_selected_hours_x", "smart_retry_selected_hours_y", "smart_retry_probability_x", "smart_retry_probability_y", "smart_retry_confidence_x", "smart_retry_confidence_y"])
        self._active_dataset = {
            "source": source,
            "dataset_id": dataset_id,
            "dataset_label": dataset_label,
            "raw_rows": raw_rows.copy(),
            "inference": inference,
            "comparison": merged_comparison,
            "transactions": transactions,
            "observed_outcome_data_available": comparison is not None and not comparison.empty,
        }

    @staticmethod
    def _inference_transactions(raw_rows: pd.DataFrame, results: list[dict[str, Any]]) -> pd.DataFrame:
        """Build one audit-friendly inference record per selected transaction."""
        rows: list[dict[str, Any]] = []
        for index, (_, row) in enumerate(raw_rows.iterrows()):
            result = results[index] if index < len(results) else {}
            transaction_id = result.get("transaction_id") or row.get("transaction_id") or f"uploaded-{index + 1}"
            amount = pd.to_numeric(row.get("amount_inr"), errors="coerce")
            rows.append({
                "transaction_id": str(transaction_id),
                "amount_inr": float(amount) if pd.notna(amount) else 0.0,
                "decline_reason": str(row.get("decline_reason", "unknown")),
                "payment_method": str(row.get("payment_method", "unknown")),
                "smart_retry_selected_hours": result.get("selected_retry_hours"),
                "smart_retry_probability": result.get("calibrated_probability"),
                "smart_retry_confidence": result.get("confidence_tier"),
                "eligible": bool(result.get("eligible", False)),
                "inference_error": result.get("error"),
            })
        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        # Candidate-grid uploads have many source rows per transaction.  The
        # model recommendation is transaction-context based, so retain one.
        return frame.drop_duplicates("transaction_id", keep="first").reset_index(drop=True)

    def _active(self) -> dict[str, Any] | None:
        return self._active_dataset

    def _active_has_outcomes(self) -> bool:
        active = self._active()
        return bool(active and active.get("comparison") is not None and not active["comparison"].empty)

    @staticmethod
    def _dataset_metadata(active: dict[str, Any] | None) -> dict[str, Any]:
        if active is None:
            return {
                "source": "demo",
                "dataset_id": "phase6_demo_artifacts",
                "dataset_label": "Validated demo evaluation dataset",
                "dataset_source": "evaluation_artifacts",
                "observed_outcome_data_available": True,
            }
        return {
            "source": active.get("source", "upload"),
            "dataset_id": active.get("dataset_id", active.get("source", "upload")),
            "dataset_label": active.get("dataset_label", "Selected uploaded CSV"),
            "dataset_source": active.get("source", "upload"),
            "observed_outcome_data_available": bool(active.get("observed_outcome_data_available")),
        }

    @staticmethod
    def _outcomes_unavailable_message() -> str:
        return (
            "This dataset has no complete observed retry outcomes for the fixed and "
            "Smart Retry candidate times. Showing inference recommendations only; "
            "recovery and revenue-impact metrics are unavailable."
        )

    def _required(self, filename: str) -> Path:
        path = self.evaluation_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Evaluation artifact is missing: {path}")
        return path

    def summary(self) -> dict:
        with self._required("phase6_summary.json").open(encoding="utf-8") as handle:
            return json.load(handle)

    def dashboard(self) -> dict:
        active = self._active()
        metadata = self._dataset_metadata(active)
        if active is not None:
            transactions = active["transactions"]
            if self._active_has_outcomes():
                summary = strategy_summary(active["comparison"])
                total = int(active["raw_rows"]["transaction_id"].nunique()) if "transaction_id" in active["raw_rows"] else len(transactions)
                payload = {
                    "total_failed_transactions": total,
                    **summary,
                    "recovered_value_lift_percent": summary["recovered_inr_lift_pct"] * 100,
                    "dataset_source": active["source"],
                    "outcome_data_available": True,
                    "outcome_unavailable_message": None,
                    "observed_outcome_data_available": True,
                    **metadata,
                }
                payload["source"] = active["source"]
                payload["dataset_id"] = active["dataset_id"]
                payload["dataset_label"] = active["dataset_label"]
                return payload
            eligible = int(transactions["eligible"].sum()) if not transactions.empty else 0
            payload = {
                "total_failed_transactions": len(transactions), "eligible_transactions": eligible,
                "fixed_recovery_transactions": 0, "smart_recovery_transactions": 0,
                "fixed_recovery_rate": 0.0, "smart_recovery_rate": 0.0,
                "fixed_recovered_inr": 0.0, "smart_recovered_inr": 0.0,
                "incremental_recovered_inr": 0.0, "incremental_recovery_rate": 0.0,
                "recovered_value_lift_percent": 0.0, "dataset_source": active["source"],
                "outcome_data_available": False,
                "outcome_unavailable_message": self._outcomes_unavailable_message(),
                "observed_outcome_data_available": False,
                **metadata,
            }
            payload["source"] = active["source"]
            payload["dataset_id"] = active["dataset_id"]
            payload["dataset_label"] = active["dataset_label"]
            return payload
        phase6 = self.summary()["summary"]
        phase3 = pd.read_csv(self._required("fixed_schedule_baseline_summary.csv")).set_index("metric")["value"]
        payload = {
            "total_failed_transactions": int(phase3["total_failed_transactions"]),
            "eligible_transactions": int(phase6["eligible_transactions"]),
            "fixed_recovery_transactions": int(phase6["fixed_recovered_transactions"]),
            "smart_recovery_transactions": int(phase6["smart_recovered_transactions"]),
            "fixed_recovery_rate": phase6["fixed_recovery_rate"],
            "smart_recovery_rate": phase6["smart_recovery_rate"],
            "fixed_recovered_inr": phase6["fixed_recovered_inr"],
            "smart_recovered_inr": phase6["smart_recovered_inr"],
            "incremental_recovered_inr": phase6["incremental_recovered_inr"],
            "incremental_recovery_rate": phase6["incremental_recovery_rate"],
            "recovered_value_lift_percent": phase6["recovered_inr_lift_pct"] * 100,
            "dataset_source": "evaluation_artifacts",
            "outcome_data_available": True,
            "outcome_unavailable_message": None,
            "observed_outcome_data_available": True,
            **metadata,
        }
        payload["source"] = "demo"
        payload["dataset_id"] = "phase6_demo_artifacts"
        payload["dataset_label"] = "Validated demo evaluation dataset"
        return payload

    def business_impact(self) -> dict:
        active = self._active()
        metadata = self._dataset_metadata(active)
        if active is not None:
            if not self._active_has_outcomes():
                payload = {
                    "fixed_schedule": {}, "smart_retry": {}, "incremental": {}, "bootstrap": {},
                    "limitations": [self._outcomes_unavailable_message()],
                    "outcome_data_available": False,
                    "outcome_unavailable_message": self._outcomes_unavailable_message(),
                    "observed_outcome_data_available": False,
                    **metadata,
                }
                payload["source"] = active["source"]
                payload["dataset_id"] = active["dataset_id"]
                payload["dataset_label"] = active["dataset_label"]
                return payload
            summary = strategy_summary(active["comparison"])
            payload = {
                "fixed_schedule": {key.removeprefix("fixed_"): value for key, value in summary.items() if key.startswith("fixed_")},
                "smart_retry": {key.removeprefix("smart_"): value for key, value in summary.items() if key.startswith("smart_")},
                "incremental": {key.removeprefix("incremental_"): value for key, value in summary.items() if key.startswith("incremental_")} | {"recovered_inr_lift_pct": summary["recovered_inr_lift_pct"]},
                "bootstrap": {},
                "limitations": ["Metrics use observed outcome labels from the selected dataset; the model was not retrained."],
                "outcome_data_available": True,
                "outcome_unavailable_message": None,
                "observed_outcome_data_available": True,
                **metadata,
            }
            payload["source"] = active["source"]
            payload["dataset_id"] = active["dataset_id"]
            payload["dataset_label"] = active["dataset_label"]
            return payload
        raw = self.summary()
        summary, bootstrap = raw["summary"], raw["bootstrap"]
        payload = {
            "fixed_schedule": {key.removeprefix("fixed_"): value for key, value in summary.items() if key.startswith("fixed_")},
            "smart_retry": {key.removeprefix("smart_"): value for key, value in summary.items() if key.startswith("smart_")},
            "incremental": {key.removeprefix("incremental_"): value for key, value in summary.items() if key.startswith("incremental_")} | {"recovered_inr_lift_pct": summary["recovered_inr_lift_pct"]},
            "bootstrap": bootstrap,
            "limitations": self._limitations(), "outcome_data_available": True,
            "outcome_unavailable_message": None,
            "observed_outcome_data_available": True,
            **metadata,
        }
        payload["source"] = "demo"
        payload["dataset_id"] = "phase6_demo_artifacts"
        payload["dataset_label"] = "Validated demo evaluation dataset"
        return payload

    def _limitations(self) -> list[str]:
        text = self._required("phase6_business_summary.md").read_text(encoding="utf-8")
        marker = "## Limitations"
        if marker not in text:
            return []
        return [line.removeprefix("- ").strip() for line in text.split(marker, 1)[1].splitlines() if line.startswith("- ")]

    def breakdown(self, dimension: str) -> list[dict]:
        files = {
            "decline_reason": "phase6_breakdown_by_decline_reason.csv",
            "decline_bucket": "phase6_breakdown_by_decline_bucket.csv",
            "payment_method": "phase6_breakdown_by_payment_method.csv",
            "amount_band": "phase6_breakdown_by_amount_band.csv",
            "confidence_tier": "phase6_breakdown_by_confidence.csv",
        }
        if dimension not in files:
            raise ValueError(f"Unsupported breakdown dimension: {dimension}")
        active = self._active()
        if active is not None:
            if not self._active_has_outcomes():
                return []
            comparison = active["comparison"].copy()
            if dimension == "amount_band":
                comparison["amount_band"] = pd.cut(
                    comparison["amount_inr"], [-np.inf, 1_000, 5_000, 20_000, np.inf],
                    labels=["under_1k", "1k_to_5k", "5k_to_20k", "20k_plus"],
                ).astype(str)
            return simulation_breakdown(comparison, dimension).to_dict(orient="records")
        return pd.read_csv(self._required(files[dimension])).to_dict(orient="records")

    def retry_distribution(self) -> dict:
        active = self._active()
        if active is not None:
            if not self._active_has_outcomes():
                return {"distribution": [], "pct_recommendations_at_24_48_72": 0.0, "pct_recommendations_outside_24_48_72": 0.0, "recovery_rate_inside_fixed_schedule_times": 0.0, "recovery_rate_outside_fixed_schedule_times": 0.0}
            comparison = active["comparison"]
            frame = simulation_breakdown(comparison, "smart_retry_selected_hours").rename(columns={"smart_retry_selected_hours": "selected_retry_hours"})
            inside = comparison["smart_retry_selected_hours"].isin([24.0, 48.0, 72.0])
            frame["selection_type"] = np.where(frame["selected_retry_hours"].isin([24.0, 48.0, 72.0]), "fixed_schedule_time", "outside_fixed_schedule")
            frame["selection_pct"] = frame["eligible_transactions"] / len(comparison)
            return {"distribution": frame.to_dict(orient="records"), "pct_recommendations_at_24_48_72": float(inside.mean()), "pct_recommendations_outside_24_48_72": float((~inside).mean()), "recovery_rate_inside_fixed_schedule_times": float(comparison.loc[inside, "smart_retry_success"].mean()), "recovery_rate_outside_fixed_schedule_times": float(comparison.loc[~inside, "smart_retry_success"].mean())}
        frame = pd.read_csv(self._required("phase6_retry_time_distribution.csv"))
        diagnostics = self.summary()["selection_diagnostics"]
        return {"distribution": frame.to_dict(orient="records"), **diagnostics}

    def confidence(self) -> list[dict]:
        active = self._active()
        if active is not None:
            # Confidence is an inference output, so its transaction counts must
            # always come from the selected dataset, even when it has no
            # observed outcome columns.
            transactions = active["transactions"]
            outcome_rows: dict[str, dict] = {}
            if self._active_has_outcomes():
                outcome_rows = {
                    str(row["smart_retry_confidence"]): row
                    for row in simulation_breakdown(active["comparison"], "smart_retry_confidence").to_dict(orient="records")
                }

            tiers: list[dict] = []
            for tier in ("High", "Medium", "Low"):
                selected = transactions.loc[
                    (transactions["eligible"] == True)
                    & (transactions["smart_retry_confidence"] == tier)
                ]
                outcome = outcome_rows.get(tier, {})
                tiers.append({
                    "smart_retry_confidence": tier,
                    "eligible_transactions": int(len(selected)),
                    "baseline_recovered_transactions": int(outcome.get("baseline_recovered_transactions", 0)),
                    "smart_retry_recovered_transactions": int(outcome.get("smart_retry_recovered_transactions", 0)),
                    "baseline_recovered_inr": float(outcome.get("baseline_recovered_inr", 0.0)),
                    "smart_retry_recovered_inr": float(outcome.get("smart_retry_recovered_inr", 0.0)),
                    "incremental_inr": float(outcome.get("incremental_inr", 0.0)),
                    "baseline_recovery_rate": float(outcome.get("baseline_recovery_rate", 0.0)),
                    "smart_retry_recovery_rate": float(outcome.get("smart_retry_recovery_rate", 0.0)),
                })
            return tiers
        return self.breakdown("confidence_tier")

    def transactions(self) -> pd.DataFrame:
        active = self._active()
        if active is not None:
            return active["comparison"].copy() if self._active_has_outcomes() else active["transactions"].copy()
        return self.evaluation_transactions()

    def evaluation_transactions(self) -> pd.DataFrame:
        """Return the immutable validated demo comparison, regardless of session."""
        return pd.read_csv(self._required("phase6_transaction_comparison.csv"))

    def audit_events(self, transaction_id: str) -> list[dict]:
        rows = self.transactions()
        match = rows.loc[rows.transaction_id.astype(str) == str(transaction_id)]
        if match.empty:
            raise KeyError(f"Unknown transaction: {transaction_id}")
        row = match.iloc[0]
        if "baseline_success" not in row:
            return [
                {"event": "original_payment_failed", "timestamp": None, "timestamp_note": "Source timestamp is not retained in the dashboard session.", "simulated": False},
                {"event": "smart_retry_recommended", "timestamp": None, "selected_retry_hours": row.get("smart_retry_selected_hours"), "calibrated_probability": row.get("smart_retry_probability"), "confidence_tier": row.get("smart_retry_confidence"), "timestamp_note": "Inference recommendation only; no observed retry outcome was provided.", "simulated": False},
            ]
        return [
            {"event": "original_payment_failed", "timestamp": None, "timestamp_note": "Observed outcome evaluation dataset.", "simulated": True},
            {"event": "fixed_schedule_evaluated", "timestamp": None, "selected_schedule_hours": row.get("baseline_selected_schedule"), "recovered": bool(row.get("baseline_success")), "simulated": True},
            {"event": "smart_retry_recommended", "timestamp": None, "selected_retry_hours": row.get("smart_retry_selected_hours"), "calibrated_probability": row.get("smart_retry_probability"), "confidence_tier": row.get("smart_retry_confidence"), "recovered": bool(row.get("smart_retry_success")), "simulated": True},
        ]
