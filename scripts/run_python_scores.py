"""Run OHI calculation and write scores to CSV."""

import argparse
import json
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ohipy.pipeline import OHIPipeline


def main():
    parser = argparse.ArgumentParser(description="Run OHI calculation and write scores to CSV")
    parser.add_argument(
        "--year",
        type=int,
        default=2024,
        help="Scenario year for the calculation (default: 2024)",
    )
    parser.add_argument(
        "--data-path",
        type=str,
        default=".",
        help="Base path for resolving config.yaml paths (default: current directory)",
    )
    parser.add_argument(
        "--weights",
        type=str,
        default=None,
        help='Goal weights as JSON string, e.g. \'{"FIS": 0.5, "MAR": 0.5}\'',
    )
    parser.add_argument(
        "--disable",
        type=str,
        default=None,
        help="Comma-separated pressure/resilience column names to disable",
    )
    parser.add_argument(
        "--skip-pressures",
        action="store_true",
        help="Skip pressure calculations (use neutral values)",
    )
    parser.add_argument(
        "--skip-resilience",
        action="store_true",
        help="Skip resilience calculations (use neutral values)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="tests/comparative/scores_2024_py.csv",
        help="Output CSV path (default: tests/comparative/scores_2024_py.csv)",
    )
    args = parser.parse_args()

    pipeline = OHIPipeline(data_path=args.data_path)

    weights = json.loads(args.weights) if args.weights else None
    disable = args.disable.split(",") if args.disable else None

    scores = pipeline.run(
        year=args.year,
        weights=weights,
        disable=disable,
        skip_pressures=args.skip_pressures,
        skip_resilience=args.skip_resilience,
    )

    scores = scores.filter(pl.col("score").is_not_null() & ~pl.col("score").is_nan())
    scores.write_csv(args.output)


if __name__ == "__main__":
    main()
