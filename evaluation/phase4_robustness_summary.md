# Phase 4 robustness validation

This pass reused saved models and the same transaction-held-out partition; no model was fitted or tuned.

- Held-out transactions: 1494
- Bootstrap resamples: 5000
- Random Forest minus original saved Logistic Regression: 0.0094; 95% CI [-0.0087, 0.0268]
- Provisional interpretation: **directionally positive but statistically uncertain**.
- HistGradientBoosting and the enhanced Logistic Regression experiment lack retained fitted pipelines or row-level held-out predictions. Their threshold and bootstrap comparisons are therefore unavailable without retraining, which this validation deliberately does not do.
