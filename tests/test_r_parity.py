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

from tests.helpers.comparison import assert_parity, compare_scores

COMPARATIVE_DIR = Path(__file__).parent / "comparative"
R_FIXTURE = COMPARATIVE_DIR / "scores_2024_r.csv"
PY_OUTPUT = COMPARATIVE_DIR / "scores_2024_py.csv"
DIFF_OUTPUT = COMPARATIVE_DIR / "scores_difference.csv"
TOLERANCE = 0.01
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


@pytest.mark.parity
def test_python_matches_r() -> None:
    """
    Compare Python scores against R reference fixture.

    This is the definitive parity test. It passes if:
      - All scores match within TOLERANCE (0.01)
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

    r_df = pl.read_csv(R_FIXTURE)
    py_df = pl.read_csv(PY_OUTPUT)

    result = compare_scores(py_df, r_df, tolerance=TOLERANCE)

    if result.failure_count > 0:
        if result.failures_df.height > 0:
            result.failures_df.write_csv(DIFF_OUTPUT)
        assert_parity(result)

    # Success - clean up any old diff file
    if DIFF_OUTPUT.exists():
        DIFF_OUTPUT.unlink()
