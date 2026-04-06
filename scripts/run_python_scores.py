"""Run calculate_all and write scores to tests/comparative/scores_2024_py.csv."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ohipy.calculate_all import calculate_all
from ohipy.config import load_config
from ohipy.layers import load_layers


def main():
    parser = argparse.ArgumentParser(description="Run OHI calculation and write scores to CSV")
    parser.add_argument(
        "--format",
        choices=["csv", "parquet"],
        help="Layer format preference (csv or parquet). Overrides config setting.",
    )
    args = parser.parse_args()

    config = load_config()

    if args.format:
        config["config"]["layer_format"] = args.format

    scores = calculate_all(config, load_layers(config))
    scores.write_csv("tests/comparative/scores_2024_py.csv")


if __name__ == "__main__":
    main()
