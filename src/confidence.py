"""Phase 5 probability calibration and confidence scoring.

The calibrator transforms probabilities from a persisted base model. It never
fits or alters that base model, and can be reused by Phase 6 scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.model import predict_success_probability, select_best_retry_time


def apply_calibrator(calibrator: Any, probabilities: pd.Series | np.ndarray) -> np.ndarray:
    """Apply a Platt or isotonic calibrator to base-model probabilities."""
    values = np.asarray(probabilities, dtype=float)
    if hasattr(calibrator, "predict_proba"):
        calibrated = calibrator.predict_proba(values.reshape(-1, 1))[:, 1]
    else:
        calibrated = calibrator.predict(values)
    return np.clip(np.asarray(calibrated, dtype=float), 0.0, 1.0)


def confidence_tier(probabilities: pd.Series | np.ndarray, low_cut: float, high_cut: float) -> pd.Series:
    """Assign evidence-derived confidence bands; cuts come from train-side validation."""
    values = np.asarray(probabilities, dtype=float)
    tiers = np.where(values < low_cut, "Low", np.where(values < high_cut, "Medium", "High"))
    return pd.Series(tiers, index=getattr(probabilities, "index", None), name="confidence_tier")


@dataclass
class CalibratedRetryModel:
    """Persisted base pipeline + learned probability calibrator + tier policy."""

    base_model: Any
    calibrator: Any
    calibration_method: str
    low_confidence_cut: float
    high_confidence_cut: float

    def predict_uncalibrated_probability(self, candidates: pd.DataFrame) -> pd.Series:
        return predict_success_probability(self.base_model, candidates)

    def predict_calibrated_probability(self, candidates: pd.DataFrame) -> pd.Series:
        raw = self.predict_uncalibrated_probability(candidates)
        return pd.Series(apply_calibrator(self.calibrator, raw), index=candidates.index, name="calibrated_probability")

    def score_candidates(self, candidates: pd.DataFrame) -> pd.DataFrame:
        """Return candidate rows with uncalibrated, calibrated, and tier outputs."""
        scored = candidates.copy()
        scored["uncalibrated_probability"] = self.predict_uncalibrated_probability(candidates)
        scored["calibrated_probability"] = self.predict_calibrated_probability(candidates)
        scored["confidence_tier"] = confidence_tier(
            scored["calibrated_probability"], self.low_confidence_cut, self.high_confidence_cut
        )
        return scored

    def select_retry_time(self, candidates: pd.DataFrame) -> pd.DataFrame:
        """Choose one candidate per transaction using calibrated probability."""
        scored = self.score_candidates(candidates)
        chosen = scored.rename(columns={"calibrated_probability": "predicted_success_probability"})
        selected = select_best_retry_time(chosen)
        return selected.rename(columns={"predicted_success_probability": "calibrated_probability"})


def estimate_confidence(predictions: pd.DataFrame) -> pd.DataFrame:
    """Compatibility helper for scored rows containing calibrated probabilities."""
    required = {"calibrated_probability", "confidence_tier"}
    if not required.issubset(predictions.columns):
        raise ValueError("Use CalibratedRetryModel.score_candidates to produce calibrated confidence tiers.")
    return predictions
