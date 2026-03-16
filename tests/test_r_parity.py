"""R parity validation tests for OHIRunner."""

import polars as pl
import pytest


def test_runner_matches_calculate_all(runner, config, layers):
    """Test that OHIRunner produces same output as direct calculate_all()."""
    from ohipy.calculate_all import calculate_all

    scores_direct = calculate_all(config, layers)
    scores_runner = runner.run(year=2024, layers=layers["data"])

    direct_sorted = scores_direct.sort(["goal", "dimension", "region_id"])
    runner_sorted = scores_runner.sort(["goal", "dimension", "region_id"])

    assert direct_sorted.shape == runner_sorted.shape
    assert list(direct_sorted.columns) == list(runner_sorted.columns)

    joined = direct_sorted.join(
        runner_sorted,
        on=["goal", "dimension", "region_id"],
        suffix="_runner",
    )

    diff = joined.filter(pl.col("score").is_nan() != pl.col("score_runner").is_nan())
    assert len(diff) == 0, f"Found {len(diff)} rows with NaN mismatches"

    diff = joined.filter(
        pl.col("score").is_finite()
        & pl.col("score_runner").is_finite()
        & ((pl.col("score") - pl.col("score_runner")).abs() > 1e-6)
    )
    assert len(diff) == 0, f"Found {len(diff)} rows with differences > 1e-6"


def test_runner_matches_r_fixture(runner, layers):
    """Test that OHIRunner output matches R fixture within tolerance."""
    from pathlib import Path

    import pandas as pd

    scores_py = runner.run(year=2024, layers=layers["data"])

    r_fixture_path = Path(__file__).parent.parent / "comparative" / "scores_2024_r.csv"
    scores_r = pd.read_csv(r_fixture_path)

    scores_py_pd = scores_py.to_pandas()

    merged = scores_py_pd.merge(
        scores_r,
        on=["region_id", "goal", "dimension"],
        suffixes=("_py", "_r"),
    )

    merged["diff"] = (merged["score_py"] - merged["score_r"]).abs()
    max_diff = merged["diff"].max()

    assert max_diff < 0.05, f"Max difference {max_diff} exceeds tolerance 0.05"
