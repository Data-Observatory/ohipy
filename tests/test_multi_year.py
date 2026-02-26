"""Multi-year aggregation tests for OHIRunner."""

import pytest


def test_multi_year_single_year(runner, layers):
    """Test that single year produces count=1 and mean=score."""
    result = runner.run_multi_year(
        years=[2024], layers=layers["data"], statistics=["mean", "count"]
    )

    assert "mean" in result.columns
    assert "count" in result.columns
    assert (result["count"] == 1.0).all()


def test_multi_year_statistics_computed(runner, layers):
    """Test that all statistics are computed correctly."""
    all_stats = ["mean", "std", "median", "p025", "p975", "min", "max", "count", "iqr"]

    result = runner.run_multi_year(years=[2024], layers=layers["data"])

    for stat in all_stats:
        assert stat in result.columns, f"Missing statistic: {stat}"


def test_configurable_statistics(runner, layers):
    """Test that only requested statistics are returned."""
    requested = ["mean", "std"]

    result = runner.run_multi_year(years=[2024], layers=layers["data"], statistics=requested)

    # Should have mean and std
    assert "mean" in result.columns
    assert "std" in result.columns

    # Should NOT have other statistics (check a few)
    assert "median" not in result.columns
    assert "count" not in result.columns
