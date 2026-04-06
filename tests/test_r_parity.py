"""R vs Python parity test - SINGLE SOURCE OF TRUTH.

This test compares Python output against R reference fixture.
It mirrors the logic in tests/comparative/compare_scores.py.

If this test FAILS:
  1. Check tests/comparative/scores_difference.csv for detailed breakdown
  2. Run: uv run python tests/comparative/compare_scores.py
"""

import os
import subprocess
from pathlib import Path

import polars as pl
import pytest

COMPARATIVE_DIR = Path(__file__).parent / "comparative"
R_FIXTURE = COMPARATIVE_DIR / "scores_2024_r.csv"
PY_OUTPUT = COMPARATIVE_DIR / "scores_2024_py.csv"
DIFF_OUTPUT = COMPARATIVE_DIR / "scores_difference.csv"
TOLERANCE = 0.05
AUTO_GEN = os.environ.get("OHI_AUTO_GENERATE_FIXTURES", "") == "1"


def _generate_r_fixture() -> None:
    """Generate R reference fixture using Docker.

    Replicates the logic from tests/comparative/calculate_scores.r.
    Raises RuntimeError if Docker execution fails.
    """
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{Path.cwd()}:/home/project",
        "-w",
        "/home/project",
        "ohicore-r-env",
        "Rscript",
        "tests/comparative/calculate_scores.r",
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        print("R fixture generated successfully")
    except subprocess.CalledProcessError as e:
        msg = [
            "\nR fixture generation failed!",
            f"Command: {' '.join(cmd)}",
            f"Exit code: {e.returncode}",
            f"Stderr: {e.stderr[-500:]}" if e.stderr else "No stderr",
        ]
        raise RuntimeError("\n".join(msg)) from e


def _generate_py_scores() -> None:
    """Generate Python scores using uv run.

    Calls scripts/run_python_scores.py.
    Raises RuntimeError if execution fails.
    """
    cmd = ["uv", "run", "python", "scripts/run_python_scores.py"]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        print("Python scores generated successfully")
    except subprocess.CalledProcessError as e:
        msg = [
            "\nPython scores generation failed!",
            f"Command: {' '.join(cmd)}",
            f"Exit code: {e.returncode}",
            f"Stderr: {e.stderr[-500:]}" if e.stderr else "No stderr",
        ]
        raise RuntimeError("\n".join(msg)) from e


def test_python_matches_r() -> None:
    """
    Compare Python scores against R reference fixture.

    This is the definitive parity test. It passes if:
      - All scores match within TOLERANCE (0.05)
      - Same number of rows in both outputs

    On failure, check tests/comparative/scores_difference.csv for:
      - Which goals have differences
      - Mean/max/min differences per goal
    """
    if not R_FIXTURE.exists():
        if AUTO_GEN:
            print(f"R fixture not found, generating: {R_FIXTURE}")
            _generate_r_fixture()
        else:
            pytest.skip(f"R fixture not found: {R_FIXTURE}")

    if not PY_OUTPUT.exists():
        if AUTO_GEN:
            print(f"Python output not found, generating: {PY_OUTPUT}")
            _generate_py_scores()
        else:
            fail_msg = (
                f"Python output not found: {PY_OUTPUT}\n"
                f"Run: uv run python scripts/run_python_scores.py"
            )
            pytest.fail(fail_msg)

    r_df = pl.read_csv(R_FIXTURE).with_columns(pl.col("score").round(2))
    py_df = pl.read_csv(PY_OUTPUT).with_columns(pl.col("score").round(2))

    merged = py_df.join(r_df, on=["region_id", "goal", "dimension"], suffix="_r")
    merged = merged.with_columns((pl.col("score") - pl.col("score_r")).abs().alias("diff"))

    # Check for NaN mismatches (Python has NaN, R has value)
    nan_failures = merged.filter(pl.col("score").is_nan() & ~pl.col("score_r").is_nan())
    value_failures = merged.filter(
        ~pl.col("score").is_nan() & ~pl.col("score_r").is_nan() & (pl.col("diff") > TOLERANCE)
    )
    failures = pl.concat([nan_failures, value_failures])

    if len(failures) > 0:
        failure_summary = (
            failures.group_by(["goal", "dimension"])
            .agg(
                [
                    pl.len().alias("count"),
                    pl.col("diff").max().alias("max_diff"),
                    pl.col("diff").mean().alias("mean_diff"),
                ]
            )
            .sort("max_diff", descending=True)
        )

        # Write detailed differences to file
        failures.write_csv(DIFF_OUTPUT)

        msg = [
            f"\n{'=' * 60}",
            f"PARITY FAILURE: {len(failures)} scores differ by > {TOLERANCE}",
            f"{'=' * 60}",
            "\nWorst offenders (goal/dimension):",
        ]

        for row in failure_summary.head(10).iter_rows(named=True):
            msg.append(
                f"  {row['goal']:6s} / {row['dimension']:10s}: "
                f"max_diff={row['max_diff']:.4f}, count={row['count']}"
            )

        msg.append(f"\nFull details written to: {DIFF_OUTPUT}")
        msg.append("Run: uv run python tests/comparative/compare_scores.py")

        pytest.fail("\n".join(msg))

    # Success - clean up any old diff file
    if DIFF_OUTPUT.exists():
        DIFF_OUTPUT.unlink()
