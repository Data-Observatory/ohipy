"""Unit tests for the comparison helper module (tests/helpers/comparison.py).

Tests cover: outer join missing-row detection, symmetric NaN handling,
key uniqueness assertion, tolerance boundaries, rounding behavior,
failure report formatting, and assert_parity.
"""

import polars as pl
import pytest

from tests.helpers.comparison import assert_parity, compare_scores, format_failure_report


@pytest.mark.integrity
class TestOuterJoinMissingRows:
    def test_outer_join_detects_py_missing_rows(self):
        """Rows in R that are not in Python should be detected."""
        py_df = pl.DataFrame(
            {
                "region_id": [0, 1, 2],
                "goal": ["FIS", "FIS", "FIS"],
                "dimension": ["score", "score", "score"],
                "score": [80.0, 75.0, 70.0],
            }
        )
        r_df = pl.DataFrame(
            {
                "region_id": [0, 1, 2, 3],
                "goal": ["FIS", "FIS", "FIS", "FIS"],
                "dimension": ["score", "score", "score", "score"],
                "score": [80.0, 75.0, 70.0, 65.0],
            }
        )
        result = compare_scores(py_df, r_df, tolerance=0.01)
        assert result.py_missing_count == 1
        assert result.failure_count >= 1

    def test_outer_join_detects_r_missing_rows(self):
        """Rows in Python that are not in R should be detected."""
        py_df = pl.DataFrame(
            {
                "region_id": [0, 1, 2, 3],
                "goal": ["FIS", "FIS", "FIS", "FIS"],
                "dimension": ["score", "score", "score", "score"],
                "score": [80.0, 75.0, 70.0, 65.0],
            }
        )
        r_df = pl.DataFrame(
            {
                "region_id": [0, 1, 2],
                "goal": ["FIS", "FIS", "FIS"],
                "dimension": ["score", "score", "score"],
                "score": [80.0, 75.0, 70.0],
            }
        )
        result = compare_scores(py_df, r_df, tolerance=0.01)
        assert result.r_missing_count == 1
        assert result.failure_count >= 1


@pytest.mark.integrity
class TestNanHandling:
    def test_both_nan_passes(self):
        """When both sides are NaN, it should not be counted as a failure."""
        py_df = pl.DataFrame(
            {
                "region_id": [0, 1],
                "goal": ["FIS", "FIS"],
                "dimension": ["score", "score"],
                "score": [float("nan"), 75.0],
            }
        )
        r_df = pl.DataFrame(
            {
                "region_id": [0, 1],
                "goal": ["FIS", "FIS"],
                "dimension": ["score", "score"],
                "score": [float("nan"), 75.0],
            }
        )
        result = compare_scores(py_df, r_df, tolerance=0.01)
        assert result.nan_mismatch_count == 0
        assert result.failure_count == 0

    def test_one_sided_nan_py_has_nan_r_has_value(self):
        """Python NaN + R value should be a NaN mismatch."""
        py_df = pl.DataFrame(
            {
                "region_id": [0, 1],
                "goal": ["FIS", "FIS"],
                "dimension": ["score", "score"],
                "score": [float("nan"), 75.0],
            }
        )
        r_df = pl.DataFrame(
            {
                "region_id": [0, 1],
                "goal": ["FIS", "FIS"],
                "dimension": ["score", "score"],
                "score": [80.0, 75.0],
            }
        )
        result = compare_scores(py_df, r_df, tolerance=0.01)
        assert result.nan_mismatch_count == 1
        assert result.failure_count >= 1

    def test_one_sided_nan_r_has_nan_py_has_value(self):
        """R NaN + Python value should be a NaN mismatch."""
        py_df = pl.DataFrame(
            {
                "region_id": [0, 1],
                "goal": ["FIS", "FIS"],
                "dimension": ["score", "score"],
                "score": [80.0, 75.0],
            }
        )
        r_df = pl.DataFrame(
            {
                "region_id": [0, 1],
                "goal": ["FIS", "FIS"],
                "dimension": ["score", "score"],
                "score": [float("nan"), 75.0],
            }
        )
        result = compare_scores(py_df, r_df, tolerance=0.01)
        assert result.nan_mismatch_count == 1
        assert result.failure_count >= 1


@pytest.mark.integrity
def test_duplicate_keys_raise():
    """Duplicate keys in either side should raise AssertionError."""
    py_df = pl.DataFrame(
        {
            "region_id": [0, 0],
            "goal": ["FIS", "FIS"],
            "dimension": ["score", "score"],
            "score": [80.0, 85.0],
        }
    )
    r_df = pl.DataFrame(
        {
            "region_id": [0],
            "goal": ["FIS"],
            "dimension": ["score"],
            "score": [80.0],
        }
    )
    with pytest.raises(AssertionError, match="[Dd]uplicate"):
        _ = compare_scores(py_df, r_df, tolerance=0.01)


@pytest.mark.integrity
def test_tolerance_boundary():
    """Diff below tolerance passes; diff above tolerance fails."""
    # Below tolerance — should PASS (diff=0.005, well within 0.01)
    py_below = pl.DataFrame(
        {"region_id": [0], "goal": ["FIS"], "dimension": ["score"], "score": [75.0]}
    )
    r_below = pl.DataFrame(
        {"region_id": [0], "goal": ["FIS"], "dimension": ["score"], "score": [75.005]}
    )
    result_below = compare_scores(py_below, r_below, tolerance=0.01)
    assert result_below.failure_count == 0

    # Above tolerance — should FAIL (diff=0.05, exceeds 0.01)
    py_above = pl.DataFrame(
        {"region_id": [0], "goal": ["FIS"], "dimension": ["score"], "score": [75.0]}
    )
    r_above = pl.DataFrame(
        {"region_id": [0], "goal": ["FIS"], "dimension": ["score"], "score": [75.05]}
    )
    result_above = compare_scores(py_above, r_above, tolerance=0.01)
    assert result_above.failure_count == 1


@pytest.mark.integrity
def test_rounding_before_compare():
    """Scores should be rounded to 2dp before comparison."""
    py_df = pl.DataFrame(
        {"region_id": [0], "goal": ["FIS"], "dimension": ["score"], "score": [75.004]}
    )
    r_df = pl.DataFrame(
        {"region_id": [0], "goal": ["FIS"], "dimension": ["score"], "score": [75.005]}
    )
    result = compare_scores(py_df, r_df, tolerance=0.01)
    # After rounding: 75.00 vs 75.01 (polars round), diff=0.01, at tolerance
    assert result.failure_count == 0


@pytest.mark.integrity
def test_format_failure_report_groups_by_dimension():
    """Failure report should list failures grouped by dimension then goal."""
    py_df = pl.DataFrame(
        {
            "region_id": [0, 1],
            "goal": ["FIS", "MAR"],
            "dimension": ["score", "status"],
            "score": [80.0, 75.0],
        }
    )
    r_df = pl.DataFrame(
        {
            "region_id": [0, 1],
            "goal": ["FIS", "MAR"],
            "dimension": ["score", "status"],
            "score": [70.0, 65.0],
        }
    )
    result = compare_scores(py_df, r_df, tolerance=0.01)
    report = format_failure_report(result, dataset="test_dataset", variation="baseline")
    assert "test_dataset" in report
    assert "2 scores differ" in report
    assert result.summary_df.height > 0


@pytest.mark.integrity
def test_assert_parity_raises_on_failure():
    """assert_parity should raise AssertionError with formatted report."""
    py_df = pl.DataFrame(
        {"region_id": [0], "goal": ["FIS"], "dimension": ["score"], "score": [80.0]}
    )
    r_df = pl.DataFrame(
        {"region_id": [0], "goal": ["FIS"], "dimension": ["score"], "score": [70.0]}
    )
    result = compare_scores(py_df, r_df, tolerance=0.01)
    with pytest.raises(AssertionError):
        assert_parity(result)


@pytest.mark.integrity
def test_mixed_nan_and_none_in_failures():
    """Regression test: failures_df construction handles mixed None/NaN values.

    Previously this raised:
        polars.exceptions.ComputeError: could not append value: NaN of type: f64
    when failures_list contained dicts with both None and float('nan') for the
    same column across different rows.
    """
    # Create scenario with: one missing row (None), one NaN mismatch (nan), one value diff (float)
    py_df = pl.DataFrame(
        {
            "region_id": [0, 1, 2],
            "goal": ["FIS", "MAR", "NP"],
            "dimension": ["score", "score", "score"],
            "score": [80.0, float("nan"), 75.0],
        }
    )
    r_df = pl.DataFrame(
        {
            "region_id": [0, 1, 2, 3],  # region_id 3 missing from Python
            "goal": ["FIS", "MAR", "NP", "TR"],
            "dimension": ["score", "score", "score", "score"],
            "score": [80.0, 70.0, 85.0, 60.0],  # MAR: nan vs 70.0 (NaN mismatch)
        }
    )
    result = compare_scores(py_df, r_df, tolerance=0.01)
    # Should not raise; verify expected failure counts
    assert result.failure_count == 3  # py_missing (TR) + nan_mismatch (MAR) + value_diff (NP)
    assert result.py_missing_count == 1
    assert result.nan_mismatch_count == 1
    # failures_df should be constructible with mixed None/NaN/float values
    assert result.failures_df.height == 3
    # Verify column types are consistent
    assert result.failures_df.schema["score_py"] == pl.Float64
    assert result.failures_df.schema["score_r"] == pl.Float64
    assert result.failures_df.schema["diff"] == pl.Float64
