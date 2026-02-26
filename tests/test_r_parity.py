"""R parity validation tests for OHIRunner."""

import pandas as pd
import pytest


def test_runner_matches_calculate_all(runner, config, layers):
    """Test that OHIRunner produces same output as direct calculate_all()."""
    from ohipy.calculate_all import calculate_all

    # Direct call
    scores_direct = calculate_all(config, layers)

    # Via runner
    scores_runner = runner.run(year=2024, layers=layers["data"])

    # Compare
    pd.testing.assert_frame_equal(scores_direct, scores_runner)


def test_runner_matches_r_fixture(runner, layers):
    """Test that OHIRunner output matches R fixture within tolerance."""
    from pathlib import Path

    # Run via OHIRunner
    scores_py = runner.run(year=2024, layers=layers["data"])

    # Load R fixture
    r_fixture_path = Path(__file__).parent.parent / "comparative" / "scores_2024_r.csv"
    scores_r = pd.read_csv(r_fixture_path)

    # Merge on (region_id, goal, dimension)
    merged = scores_py.merge(
        scores_r,
        on=["region_id", "goal", "dimension"],
        suffixes=("_py", "_r"),
    )

    # Check max difference within tolerance
    merged["diff"] = (merged["score_py"] - merged["score_r"]).abs()
    max_diff = merged["diff"].max()

    assert max_diff < 0.05, f"Max difference {max_diff} exceeds tolerance 0.05"
