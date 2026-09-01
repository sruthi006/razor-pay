"""Run Phase 3 fixed-schedule baseline on the authoritative synthetic CSV."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.baseline import (  # noqa: E402
    load_and_validate_dataset,
    save_baseline_artifacts,
    simulate_fixed_schedule,
    summarize_baseline,
)

DEFAULT_INPUT = ROOT / "data" / "raw" / "final_prototype_100k_corrected.csv"
DEFAULT_OUTPUT_DIR = ROOT / "evaluation"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fixed T+1/T+2/T+3 baseline.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    dataset, warnings = load_and_validate_dataset(args.input)
    outcomes = simulate_fixed_schedule(dataset)
    metrics = summarize_baseline(outcomes)
    outcomes_path, metrics_path = save_baseline_artifacts(outcomes, metrics, args.output_dir)

    print("=== Phase 3 fixed-schedule baseline ===")
    print(metrics.to_string(index=False))
    print("\nValidation warnings:")
    print("- none" if not warnings else "\n".join(f"- {warning}" for warning in warnings))
    print(f"\nOutcomes: {outcomes_path}")
    print(f"Summary: {metrics_path}")


if __name__ == "__main__":
    main()
