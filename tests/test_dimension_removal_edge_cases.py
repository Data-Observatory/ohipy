"""Edge case and boundary condition tests for pressure/resilience removal.

Tests behaviors around nonexistent columns, empty disable lists, case sensitivity,
all-column removal, and cross-dimension preservation.

These tests document current behavior for ConfigOverlay edge cases.
"""

from __future__ import annotations

import polars as pl
import pytest

# =============================================================================
# Helpers
# =============================================================================


def _get_pressure_cols(config: dict[str, object]) -> list[str]:
    """Extract pressure column names from the pressures matrix."""
    pm: pl.DataFrame = config["pressures_matrix"]  # pyright: ignore[reportAssignmentType]
    return [c for c in pm.columns if c not in ["goal", "element", "element_name"]]


def _get_resilience_cols(config: dict[str, object]) -> list[str]:
    """Extract resilience column names from the resilience matrix."""
    rm: pl.DataFrame = config["resilience_matrix"]  # pyright: ignore[reportAssignmentType]
    return [c for c in rm.columns if c not in ["goal", "element", "element_name"]]


def _scores_are_identical(a: pl.DataFrame, b: pl.DataFrame) -> bool:
    """Check if two score DataFrames have identical scores (within float tolerance).

    Joins on (region_id, goal, dimension) and verifies all scores match
    within tolerance of 1e-12. NaN values are treated as equal: both-NaN
    = match, one-NaN = mismatch. Floating point non-determinism between
    identical runs can produce differences up to ~1e-14.
    """
    key_cols = ["region_id", "goal", "dimension"]
    for col_name in key_cols:
        assert col_name in a.columns, f"Missing column in a: {col_name}"
        assert col_name in b.columns, f"Missing column in b: {col_name}"

    joined = a.join(
        b,
        on=key_cols,
        how="full",
        suffix="_b",
    )

    score_a = joined["score"]
    score_b = joined["score_b"]

    a_is_nan = score_a.is_nan() | score_a.is_null()
    b_is_nan = score_b.is_nan() | score_b.is_null()
    both_nan = a_is_nan & b_is_nan
    one_nan = (a_is_nan | b_is_nan) & ~both_nan

    if one_nan.any():
        return False

    non_nan_mask = ~a_is_nan & ~b_is_nan
    if non_nan_mask.any():
        max_diff = (
            joined.filter(non_nan_mask)
            .select((pl.col("score") - pl.col("score_b")).abs().alias("diff"))
            .select(pl.col("diff").max())
            .item()
        )
        if max_diff is not None and max_diff > 1e-12:
            return False

    return True


# =============================================================================
# Edge Case Tests
# =============================================================================


def test_disable_nonexistent_pressure_column(runner, config, layers):
    """Disabling a nonexistent pressure column is a silent no-op.

    Current behavior: ConfigOverlay.apply_disable filters column names via
    list comprehension, so unknown names are silently ignored.
    """
    baseline = runner.run(year=2024, layers=layers["data"])

    overrides = {"disable": {"pressures": ["fake_pressure_column"], "resiliences": []}}
    modified = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert _scores_are_identical(baseline, modified), (
        "Disabling a nonexistent pressure column should be a no-op "
        "(scores identical to baseline)"
    )


def test_disable_nonexistent_resilience_column(runner, config, layers):
    """Disabling a nonexistent resilience column is a silent no-op.

    Current behavior: same as pressure side — unknown names silently ignored.
    """
    baseline = runner.run(year=2024, layers=layers["data"])

    overrides = {"disable": {"pressures": [], "resiliences": ["fake_resilience_column"]}}
    modified = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert _scores_are_identical(baseline, modified), (
        "Disabling a nonexistent resilience column should be a no-op "
        "(scores identical to baseline)"
    )


def test_disable_all_pressures_raises(runner, config, layers):
    """Removing ALL pressure columns raises ValueError."""
    all_pressure_cols = _get_pressure_cols(config)
    overrides = {"disable": {"pressures": all_pressure_cols, "resiliences": []}}
    with pytest.raises(ValueError, match="No pressure layer data found"):
        runner.run(year=2024, layers=layers["data"], overrides=overrides)


def test_disable_all_resiliences_raises(runner, config, layers):
    """Removing ALL resilience columns raises ValueError."""
    all_resilience_cols = _get_resilience_cols(config)
    overrides = {"disable": {"pressures": [], "resiliences": all_resilience_cols}}
    with pytest.raises(ValueError, match="No resilience layer data found"):
        runner.run(year=2024, layers=layers["data"], overrides=overrides)


def test_empty_disable_list_matches_baseline(runner, config, layers):
    """Passing empty disable lists produces identical scores to no overrides."""
    baseline = runner.run(year=2024, layers=layers["data"])

    overrides = {"disable": {"pressures": [], "resiliences": []}}
    modified = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert _scores_are_identical(baseline, modified), (
        "Empty disable lists should produce scores identical to baseline"
    )


def test_disable_case_sensitivity(runner, config, layers):
    """Column names are case-sensitive; wrong case is treated as nonexistent.

    Pressure columns use lowercase (e.g., 'cw_conquimica'), so disabling with
    uppercase (e.g., 'CW_CONQUIMICA') is a silent no-op.
    """
    baseline = runner.run(year=2024, layers=layers["data"])

    overrides = {"disable": {"pressures": ["CW_CONQUIMICA"], "resiliences": []}}
    modified = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert _scores_are_identical(baseline, modified), (
        "Disabling 'CW_CONQUIMICA' (uppercase) should be a no-op since the "
        "real column name is 'cw_conquimica' (lowercase)"
    )


def test_disable_pressure_preserves_resilience_dimension(runner, config, layers):
    """Disabling a pressure column must not affect resilience scores."""
    pressure_cols = _get_pressure_cols(config)
    first_pressure = pressure_cols[0]

    baseline = runner.run(year=2024, layers=layers["data"])

    overrides = {"disable": {"pressures": [first_pressure], "resiliences": []}}
    modified = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    # Resilience dimension must be present
    resilience_modified = modified.filter(pl.col("dimension") == "resilience")
    assert resilience_modified.height > 0, (
        "Resilience dimension scores should still exist after disabling a pressure"
    )

    # Resilience scores must match baseline exactly
    baseline_resilience = baseline.filter(pl.col("dimension") == "resilience")
    assert _scores_are_identical(baseline_resilience, resilience_modified), (
        f"Resilience scores must be unchanged when disabling pressure '{first_pressure}'"
    )


def test_disable_resilience_preserves_pressure_dimension(runner, config, layers):
    """Disabling a resilience column must not affect pressure scores."""
    resilience_cols = _get_resilience_cols(config)
    first_resilience = resilience_cols[0]

    baseline = runner.run(year=2024, layers=layers["data"])

    overrides = {"disable": {"pressures": [], "resiliences": [first_resilience]}}
    modified = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    # Pressure dimension must be present
    pressure_modified = modified.filter(pl.col("dimension") == "pressures")
    assert pressure_modified.height > 0, (
        "Pressure dimension scores should still exist after disabling a resilience"
    )

    # Pressure scores must match baseline exactly
    baseline_pressure = baseline.filter(pl.col("dimension") == "pressures")
    assert _scores_are_identical(baseline_pressure, pressure_modified), (
        f"Pressure scores must be unchanged when disabling resilience '{first_resilience}'"
    )
