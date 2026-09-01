"""Generate the Phase 2A prototype CSV (~10k candidate-level rows)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_generation import (  # noqa: E402
    generate_prototype_dataset,
    print_validation_report,
    save_dataset,
)

DEFAULT_OUT = ROOT / "data" / "raw" / "prototype_transactions.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate prototype synthetic retry dataset.")
    parser.add_argument("--n-rows", type=int, default=10_000, help="Target row count (~grid-aligned).")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    df = generate_prototype_dataset(n_rows=args.n_rows, seed=args.seed)
    out = save_dataset(df, args.output)
    print_validation_report(df)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
