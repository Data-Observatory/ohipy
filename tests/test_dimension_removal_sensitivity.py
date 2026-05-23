"""Dimension removal sensitivity tests.

Verify scores actually change when individual pressure/resilience columns
are removed from the calculation matrices.
"""

import polars as pl
import pytest

from ohipy.config import load_config as _load_config

pytestmark = pytest.mark.slow

# ── Module-level column lists (computed once at import) ──

_config = _load_config()

_pm: pl.DataFrame = _config["pressures_matrix"]  # pyright: ignore[reportAssignmentType]
PRESSURE_COLS = [c for c in _pm.columns if c not in ("goal", "element", "element_name")]

_rm: pl.DataFrame = _config["resilience_matrix"]  # pyright: ignore[reportAssignmentType]
RESILIENCE_COLS = [c for c in _rm.columns if c not in ("goal", "element", "element_name")]


# ── Helper ──


def _count_score_differences(baseline: pl.DataFrame, modified: pl.DataFrame) -> int:
    """Count rows where non-NaN scores differ between baseline and modified.

    Rows where both sides are null or both are NaN are considered equal.
    """
    joined = baseline.join(
        modified,
        on=["region_id", "goal", "dimension"],
        how="inner",
        suffix="_mod",
    )
    same = (
        (pl.col("score").is_null() & pl.col("score_mod").is_null())
        | (pl.col("score").is_nan() & pl.col("score_mod").is_nan())
        | (
            pl.col("score").is_not_null()
            & pl.col("score_mod").is_not_null()
            & (pl.col("score") == pl.col("score_mod"))
        )
    )
    diff = joined.filter(~same)
    return diff.height


# ── Baseline (computed once via module-level cache) ──

_baseline_cache: pl.DataFrame | None = None


@pytest.fixture
def baseline_scores(runner, layers):
    """Run baseline calculation once per session via module-level cache."""
    global _baseline_cache
    if _baseline_cache is None:
        _baseline_cache = runner.run(year=2024, layers=layers["data"])
    return _baseline_cache


# ── Parametrized pressure sensitivity tests ──


@pytest.mark.parametrize("pressure_col", PRESSURE_COLS)
def test_pressure_removal_changes_scores(
    runner, layers, baseline_scores, pressure_col
):
    """Removing a pressure column should change at least one score."""
    overrides = {"disable": {"pressures": [pressure_col], "resiliences": []}}
    modified = runner.run(year=2024, layers=layers["data"], overrides=overrides)
    diff_count = _count_score_differences(baseline_scores, modified)
    assert diff_count > 0, f"Removing pressure '{pressure_col}' changed no scores"


# ── Parametrized resilience sensitivity tests ──


@pytest.mark.parametrize("resilience_col", RESILIENCE_COLS)
def test_resilience_removal_changes_scores(
    runner, layers, baseline_scores, resilience_col
):
    """Removing a resilience column should change at least one score."""
    overrides = {"disable": {"pressures": [], "resiliences": [resilience_col]}}
    modified = runner.run(year=2024, layers=layers["data"], overrides=overrides)
    diff_count = _count_score_differences(baseline_scores, modified)
    assert diff_count > 0, (
        f"Removing resilience '{resilience_col}' changed no scores"
    )


# ── Directional sanity tests ──


def test_pressure_removal_increases_or_maintains_index(
    runner, layers, baseline_scores
):
    """Removing a pressure should increase or maintain the global Index score.

    Pressures reduce scores, so removing one should not decrease the Index.
    """
    test_col = PRESSURE_COLS[0]
    overrides = {"disable": {"pressures": [test_col], "resiliences": []}}
    modified = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    baseline_index = (
        baseline_scores.filter(
            (pl.col("goal") == "Index")
            & (pl.col("region_id") == 0)
            & (pl.col("dimension") == "score")
        )
        .select("score")
        .item(0, 0)
    )
    modified_index = (
        modified.filter(
            (pl.col("goal") == "Index")
            & (pl.col("region_id") == 0)
            & (pl.col("dimension") == "score")
        )
        .select("score")
        .item(0, 0)
    )

    assert modified_index >= baseline_index - 1e-10, (
        f"Removing pressure '{test_col}' decreased index from "
        f"{baseline_index} to {modified_index}"
    )


def test_resilience_removal_decreases_or_maintains_index(
    runner, layers, baseline_scores
):
    """Removing a resilience should decrease or maintain the global Index score.

    Resilience increases scores, so removing one should not increase the Index.
    """
    test_col = RESILIENCE_COLS[0]
    overrides = {"disable": {"pressures": [], "resiliences": [test_col]}}
    modified = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    baseline_index = (
        baseline_scores.filter(
            (pl.col("goal") == "Index")
            & (pl.col("region_id") == 0)
            & (pl.col("dimension") == "score")
        )
        .select("score")
        .item(0, 0)
    )
    modified_index = (
        modified.filter(
            (pl.col("goal") == "Index")
            & (pl.col("region_id") == 0)
            & (pl.col("dimension") == "score")
        )
        .select("score")
        .item(0, 0)
    )

    assert modified_index <= baseline_index + 1e-10, (
        f"Removing resilience '{test_col}' increased index from "
        f"{baseline_index} to {modified_index}"
    )


def test_multiple_pressure_removal_greater_effect(
    runner, layers, baseline_scores
):
    """Removing 3 pressures should change more scores than removing 1."""
    if len(PRESSURE_COLS) < 3:
        pytest.skip("Need at least 3 pressure columns for comparison")

    overrides_one = {"disable": {"pressures": [PRESSURE_COLS[0]], "resiliences": []}}
    modified_one = runner.run(year=2024, layers=layers["data"], overrides=overrides_one)
    diff_one = _count_score_differences(baseline_scores, modified_one)

    overrides_three = {
        "disable": {"pressures": PRESSURE_COLS[:3], "resiliences": []}
    }
    modified_three = runner.run(year=2024, layers=layers["data"], overrides=overrides_three)
    diff_three = _count_score_differences(baseline_scores, modified_three)

    assert diff_three >= diff_one, (
        f"Removing 3 pressures ({'{}, {}, {}'.format(*PRESSURE_COLS[:3])}) "
        f"only changed {diff_three} scores vs {diff_one} for 1 pressure "
        f"({PRESSURE_COLS[0]})"
    )


# ── Combined removal tests ──


def test_all_pressures_removed_raises(runner, layers):
    """Removing ALL pressure columns raises ValueError.

    This is expected behavior: calculate_pressures_all() cannot operate
    without any pressure layers.
    """
    overrides = {"disable": {"pressures": PRESSURE_COLS, "resiliences": []}}
    with pytest.raises(ValueError, match="No pressure layer data found"):
        runner.run(year=2024, layers=layers["data"], overrides=overrides)


def test_all_resiliences_removed_raises(runner, layers):
    """Removing ALL resilience columns raises ValueError.

    This is expected behavior: calculate_resilience_all() cannot operate
    without any resilience layers.
    """
    overrides = {"disable": {"pressures": [], "resiliences": RESILIENCE_COLS}}
    with pytest.raises(ValueError, match="No resilience layer data found"):
        runner.run(year=2024, layers=layers["data"], overrides=overrides)
