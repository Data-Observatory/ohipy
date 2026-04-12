#!/usr/bin/env python3
"""Compare Python and R OHI scores for parity."""

import subprocess
import sys
from pathlib import Path

import polars as pl

# Ensure project root is on sys.path so `tests.helpers` resolves when run as a script
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tests.helpers.comparison import compare_scores, format_failure_report  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent

REMOTE_URL = (
    "https://raw.githubusercontent.com/OHI-Science/chl/refs/heads/master/comunas/scores.csv"
)
LOCAL_SCORES = str(SCRIPT_DIR / "scores_2024_r.csv")
PY_SCORES = str(SCRIPT_DIR / "scores_2024_py.csv")
tolerance = 0.01


def _drop_null_nan(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter(pl.col("score").is_not_null() & ~pl.col("score").is_nan())


def main():
    r_local = pl.read_csv(LOCAL_SCORES).with_columns(pl.col("score").round(2))
    r_remote = pl.read_csv(REMOTE_URL).with_columns(pl.col("score").round(2))

    r_check = compare_scores(r_local, r_remote, tolerance=tolerance)
    if r_check.failure_count > 0:
        print(f"\nWARNING: R local vs R remote: {r_check.failure_count} differences found!")
        print("Proceeding with Python vs R local comparison.\n")
    else:
        print("SUCCESS: R local output is equal to R output at the repository")

    if not Path(PY_SCORES).exists():
        _ = subprocess.run(
            [sys.executable, "scripts/run_python_scores.py"], check=True, stdout=subprocess.DEVNULL
        )

    py_scores = _drop_null_nan(pl.read_csv(PY_SCORES)).with_columns(pl.col("score").round(2))
    r_local = _drop_null_nan(r_local)

    result = compare_scores(py_scores, r_local, tolerance=tolerance)
    if result.failure_count > 0:
        print(f"\nPython vs R: {result.failure_count} differences found!")
        print(format_failure_report(result))
        if result.failures_df.height > 0:
            result.failures_df.write_csv("tests/comparative/scores_difference.csv")
        sys.exit(1)

    print(f"\nAll scores match within tolerance {tolerance}!")
    print(f"Max absolute difference: {result.max_diff}")


if __name__ == "__main__":
    main()
