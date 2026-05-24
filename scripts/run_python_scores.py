"""Run OHI calculation and write scores to CSV or Parquet."""

import argparse
import json
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ohipy.pipeline import OHIPipeline


def _parse_years(year_arg: int, years_arg: str | None) -> list[int]:
    """Resolve --year / --years into an ordered list of ints."""
    if years_arg is not None:
        return [int(y.strip()) for y in years_arg.split(",") if y.strip()]
    return [year_arg]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run OHI calculation and write scores to CSV or Parquet"
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2024,
        help="Scenario year (default: 2024). Use --years for multiple years.",
    )
    parser.add_argument(
        "--years",
        type=str,
        default=None,
        help="Comma-separated scenario years, e.g. '2017,2018,2024'. Overrides --year.",
    )
    parser.add_argument(
        "--data-path",
        type=str,
        default=".",
        help="Base path for resolving config.yaml paths (default: current directory)",
    )
    parser.add_argument(
        "--layers-csv",
        type=str,
        default=None,
        help="Path to custom layers.csv metadata file (overrides data/layers.csv)",
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
        help="Output path. Extension determines format: .parquet → Parquet (zstd), "
             "otherwise → CSV. (default: tests/comparative/scores_2024_py.csv)",
    )
    args = parser.parse_args()

    years = _parse_years(args.year, args.years)
    weights = json.loads(args.weights) if args.weights else None
    disable = args.disable.split(",") if args.disable else None

    pipeline = OHIPipeline(data_path=args.data_path, layers_csv=args.layers_csv)

    if len(years) == 1:
        scores = pipeline.run(
            year=years[0],
            weights=weights,
            disable=disable,
            skip_pressures=args.skip_pressures,
            skip_resilience=args.skip_resilience,
        )
        scores = scores.filter(pl.col("score").is_not_null() & ~pl.col("score").is_nan())
    else:
        scores = pipeline.run_years(
            years=years,
            weights=weights,
            disable=disable,
            skip_pressures=args.skip_pressures,
            skip_resilience=args.skip_resilience,
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix == ".parquet":
        scores.write_parquet(output_path, compression="zstd")
    else:
        scores.write_csv(output_path)


if __name__ == "__main__":
    main()
