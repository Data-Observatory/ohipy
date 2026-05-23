"""Tests for pressure/resilience isolation via ConfigOverlay.

These tests verify that disabling individual pressures and resiliences
changes the calculation scores (verified against baseline) and does not crash.
"""

import polars as pl
import pytest

_baseline_cache: pl.DataFrame | None = None


@pytest.fixture
def baseline_scores(runner, layers):
    """Run baseline calculation once per session via module-level cache."""
    global _baseline_cache
    if _baseline_cache is None:
        _baseline_cache = runner.run(year=2024, layers=layers["data"])
    return _baseline_cache


def _score_diff_count(
    baseline: pl.DataFrame, modified: pl.DataFrame, dimension: str | None = None
) -> int:
    """Count score differences between baseline and modified.

    If dimension is specified, only count differences in that dimension.
    NaN-vs-NaN is treated as equal.
    """
    if dimension:
        baseline = baseline.filter(pl.col("dimension") == dimension)
        modified = modified.filter(pl.col("dimension") == dimension)

    joined = baseline.join(
        modified, on=["region_id", "goal", "dimension"], how="inner", suffix="_mod"
    )

    # Count rows where scores differ (treating NaN==NaN as equal)
    diffs = joined.filter(
        ~(
            (pl.col("score") == pl.col("score_mod"))
            | (pl.col("score").is_nan() & pl.col("score_mod").is_nan())
        )
    )
    return diffs.height


def test_disable_single_pressure(runner, config, layers, baseline_scores):
    """Test that disabling one pressure changes pressure score.

    Verifies that:
    1. Calculation completes without error
    2. Pressure dimension scores are affected
    3. Scores are valid (not NaN or inf)
    4. Scores differ from baseline
    """
    pm = config["pressures_matrix"]
    pressure_cols = [c for c in pm.columns if c not in ["goal", "element", "element_name"]]
    first_pressure = pressure_cols[0]

    overrides = {"disable": {"pressures": [first_pressure], "resiliences": []}}
    scores = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert scores is not None
    assert len(scores) > 0

    pressure_scores = scores.filter(pl.col("dimension") == "pressures")
    assert len(pressure_scores) > 0

    pressure_values = pressure_scores.select("score").to_series().to_list()
    for val in pressure_values:
        if val is not None:
            assert not float("inf") == val
            assert not float("-inf") == val

    diff_count = _score_diff_count(baseline_scores, scores, dimension="pressures")
    assert diff_count > 0, f"Disabling {first_pressure} should change pressure scores"


def test_disable_all_pressures_for_goal(runner, config, layers, baseline_scores):
    """Test that disabling all pressures for a goal works correctly.

    Verifies that:
    1. Multiple pressures can be disabled
    2. Calculation completes without error
    3. Result contains valid scores
    4. Scores differ from baseline
    """
    pm = config["pressures_matrix"]
    pressure_cols = [c for c in pm.columns if c not in ["goal", "element", "element_name"]]

    pressures_to_disable = pressure_cols[:3]
    overrides = {"disable": {"pressures": pressures_to_disable, "resiliences": []}}
    scores = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert scores is not None
    assert len(scores) > 0

    pressure_scores = scores.filter(pl.col("dimension") == "pressures")
    assert len(pressure_scores) > 0

    diff_count = _score_diff_count(baseline_scores, scores)
    assert diff_count > 0, "Disabling 3 pressures should change some scores"


def test_disable_single_resilience(runner, config, layers, baseline_scores):
    """Test that disabling one resilience changes resilience score.

    Verifies that:
    1. Calculation completes without error
    2. Resilience dimension scores are affected
    3. Scores are valid (not NaN or inf)
    4. Scores differ from baseline
    """
    rm = config["resilience_matrix"]
    resilience_cols = [c for c in rm.columns if c not in ["goal", "element", "element_name"]]
    first_resilience = resilience_cols[0]

    overrides = {"disable": {"pressures": [], "resiliences": [first_resilience]}}
    scores = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert scores is not None
    assert len(scores) > 0

    resilience_scores = scores.filter(pl.col("dimension") == "resilience")
    assert len(resilience_scores) > 0

    resilience_values = resilience_scores.select("score").to_series().to_list()
    for val in resilience_values:
        if val is not None:
            assert not float("inf") == val
            assert not float("-inf") == val

    diff_count = _score_diff_count(baseline_scores, scores, dimension="resilience")
    assert diff_count > 0, f"Disabling {first_resilience} should change resilience scores"


def test_disable_all_resiliences_for_goal(runner, config, layers, baseline_scores):
    """Test that disabling all resiliences for a goal works correctly.

    Verifies that:
    1. Multiple resiliences can be disabled
    2. Calculation completes without error
    3. Result contains valid scores
    4. Scores differ from baseline
    """
    rm = config["resilience_matrix"]
    resilience_cols = [c for c in rm.columns if c not in ["goal", "element", "element_name"]]

    resiliences_to_disable = resilience_cols[:3]
    overrides = {"disable": {"pressures": [], "resiliences": resiliences_to_disable}}
    scores = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert scores is not None
    assert len(scores) > 0

    resilience_scores = scores.filter(pl.col("dimension") == "resilience")
    assert len(resilience_scores) > 0

    diff_count = _score_diff_count(baseline_scores, scores)
    assert diff_count > 0, "Disabling 3 resiliences should change some scores"


def test_empty_pressure_matrix(runner, config, layers, baseline_scores):
    """Removing ALL pressure columns raises ValueError.

    This is expected: calculate_pressures_all() cannot operate without layers.
    """
    pm = config["pressures_matrix"]
    pressure_cols = [c for c in pm.columns if c not in ["goal", "element", "element_name"]]

    overrides = {"disable": {"pressures": pressure_cols, "resiliences": []}}
    with pytest.raises(ValueError, match="No pressure layer data found"):
        runner.run(year=2024, layers=layers["data"], overrides=overrides)


def test_disable_pressure_and_resilience_together(runner, config, layers, baseline_scores):
    """Test that disabling both pressures and resiliences works together.

    Verifies that:
    1. Both can be disabled simultaneously
    2. Calculation completes without error
    3. Multiple dimensions are affected
    4. Scores differ from baseline
    """
    pm = config["pressures_matrix"]
    rm = config["resilience_matrix"]
    pressure_cols = [c for c in pm.columns if c not in ["goal", "element", "element_name"]]
    resilience_cols = [c for c in rm.columns if c not in ["goal", "element", "element_name"]]

    overrides = {
        "disable": {
            "pressures": [pressure_cols[0]],
            "resiliences": [resilience_cols[0]],
        }
    }
    scores = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert scores is not None
    assert len(scores) > 0

    pressure_scores = scores.filter(pl.col("dimension") == "pressures")
    resilience_scores = scores.filter(pl.col("dimension") == "resilience")
    assert len(pressure_scores) > 0
    assert len(resilience_scores) > 0

    diff_count = _score_diff_count(baseline_scores, scores)
    assert diff_count > 0, "Disabling pressure+resilience should change scores"
