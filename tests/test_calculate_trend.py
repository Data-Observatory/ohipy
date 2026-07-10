"""Tests for calculate_trend (vectorized OLS trend slope)."""

import polars as pl

from ohipy.calculate import calculate_trend


def test_linear_increasing_status_gives_positive_score() -> None:
    """Perfectly linear rising status yields the exact closed-form slope-derived score."""
    df = pl.DataFrame(
        {
            "region_id": [1, 1, 1, 1, 1],
            "year": [2020, 2021, 2022, 2023, 2024],
            "status": [0.5, 0.55, 0.6, 0.65, 0.7],
        }
    )
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024])
    assert result["score"].to_list() == [0.5]


def test_linear_decreasing_status_gives_negative_score() -> None:
    """Perfectly linear falling status yields a negative score."""
    df = pl.DataFrame(
        {
            "region_id": [1, 1, 1, 1, 1],
            "year": [2020, 2021, 2022, 2023, 2024],
            "status": [0.7, 0.65, 0.6, 0.55, 0.5],
        }
    )
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024])
    assert result["score"].to_list() == [-0.3571]


def test_flat_status_gives_zero_score() -> None:
    """No change across years yields slope 0 and score 0 (explicit zero-slope branch)."""
    df = pl.DataFrame(
        {
            "region_id": [1, 1, 1, 1, 1],
            "year": [2020, 2021, 2022, 2023, 2024],
            "status": [0.6, 0.6, 0.6, 0.6, 0.6],
        }
    )
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024])
    assert result["score"].to_list() == [0.0]


def test_score_is_clipped_to_one() -> None:
    """A slope large relative to the reference status is clipped to 1.0, not left unbounded."""
    df = pl.DataFrame(
        {
            "region_id": [1, 1, 1, 1, 1],
            "year": [2020, 2021, 2022, 2023, 2024],
            "status": [0.01, 0.51, 1.01, 1.51, 2.01],
        }
    )
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024])
    assert result["score"].to_list() == [1.0]


def test_zero_reference_status_positive_slope_gives_one() -> None:
    """When the status at the reference (first trend) year is 0, score falls back to +-1 by slope sign."""
    df = pl.DataFrame(
        {
            "region_id": [1, 1, 1, 1, 1],
            "year": [2020, 2021, 2022, 2023, 2024],
            "status": [0.0, 0.05, 0.1, 0.15, 0.2],
        }
    )
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024])
    assert result["score"].to_list() == [1.0]


def test_zero_reference_status_negative_slope_gives_negative_one() -> None:
    """Same zero-reference branch, falling status, gives -1."""
    df = pl.DataFrame(
        {
            "region_id": [1, 1, 1, 1, 1],
            "year": [2020, 2021, 2022, 2023, 2024],
            "status": [0.2, 0.15, 0.1, 0.05, 0.0],
        }
    )
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024])
    assert result["score"].to_list() == [-1.0]


def test_single_year_dropped_when_no_default_trend() -> None:
    """A region with only 1 year of data (n<2) is dropped entirely when default_trend is None.

    This is the exact failure mode a collapsed 5-year window would produce: not a
    spurious 0.0, but a silently missing row.
    """
    df = pl.DataFrame({"region_id": [1], "year": [2024], "status": [0.6]})
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024], default_trend=None)
    assert result.shape[0] == 0


def test_single_year_still_dropped_even_with_default_trend() -> None:
    """A region with n<2 is dropped even when default_trend is set.

    The final filter branches on whether default_trend is None, but the non-None
    branch filters on `n >= 2` regardless of the value substituted for n<2 rows,
    so a supplied default_trend never actually surfaces for an n<2 region.
    """
    df = pl.DataFrame({"region_id": [1], "year": [2024], "status": [0.6]})
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024], default_trend=0.0)
    assert result.shape[0] == 0


def test_default_trend_surfaces_when_reference_year_missing() -> None:
    """A region present for >=2 years but missing status at the reference (first) trend
    year gets a null adjust_trend, and falls back to default_trend (kept, since n>=2)."""
    df = pl.DataFrame(
        {
            "region_id": [1, 1, 1, 1],
            "year": [2021, 2022, 2023, 2024],
            "status": [0.5, 0.55, 0.6, 0.65],
        }
    )
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024], default_trend=0.0)
    assert result["score"].to_list() == [0.0]


def test_missing_reference_year_dropped_without_default_trend() -> None:
    """Same missing-reference-year case, but with default_trend=None the row is dropped."""
    df = pl.DataFrame(
        {
            "region_id": [1, 1, 1, 1],
            "year": [2021, 2022, 2023, 2024],
            "status": [0.5, 0.55, 0.6, 0.65],
        }
    )
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024], default_trend=None)
    assert result.shape[0] == 0


def test_multiple_regions_computed_independently() -> None:
    """Each region gets its own independent slope/score."""
    df = pl.DataFrame(
        {
            "region_id": [1, 1, 1, 2, 2, 2],
            "year": [2020, 2022, 2024, 2020, 2022, 2024],
            "status": [0.5, 0.6, 0.7, 0.5, 0.5, 0.5],
        }
    )
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024]).sort("region_id")
    assert result["region_id"].to_list() == [1, 2]
    assert result["score"].to_list() == [0.5, 0.0]


def test_duplicate_region_year_rows_are_deduplicated() -> None:
    """Duplicate (region_id, year) rows are collapsed by .unique before regression."""
    df = pl.DataFrame(
        {
            "region_id": [1, 1, 1, 1, 1, 1],
            "year": [2020, 2020, 2021, 2022, 2023, 2024],
            "status": [0.5, 0.5, 0.55, 0.6, 0.65, 0.7],
        }
    )
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024])
    assert result["score"].to_list() == [0.5]


def test_renames_rgn_id_and_scenario_year_columns() -> None:
    """rgn_id/scenario_year input columns are normalized to region_id/year before computing."""
    df = pl.DataFrame(
        {
            "rgn_id": [1, 1, 1, 1, 1],
            "scenario_year": [2020, 2021, 2022, 2023, 2024],
            "status": [0.5, 0.55, 0.6, 0.65, 0.7],
        }
    )
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024])
    assert result["region_id"].to_list() == [1]
    assert result["score"].to_list() == [0.5]


def test_trend_years_none_uses_all_years_present() -> None:
    """When trend_years is not passed, all distinct years in the input are used."""
    df = pl.DataFrame(
        {
            "region_id": [1, 1, 1, 1, 1],
            "year": [2020, 2021, 2022, 2023, 2024],
            "status": [0.5, 0.55, 0.6, 0.65, 0.7],
        }
    )
    result = calculate_trend(df)
    assert result["score"].to_list() == [0.5]


def test_empty_trend_years_returns_empty_result_with_schema() -> None:
    """An explicitly empty trend_years list short-circuits to an empty, correctly-typed frame."""
    df = pl.DataFrame(
        {
            "region_id": [1, 1],
            "year": [2020, 2021],
            "status": [0.5, 0.55],
        }
    )
    result = calculate_trend(df, trend_years=[])
    assert result.shape[0] == 0
    assert result.schema == {
        "region_id": pl.Int64,
        "score": pl.Float64,
        "dimension": pl.Utf8,
    }


def test_result_has_trend_dimension_label() -> None:
    """Output rows are tagged with dimension='trend'."""
    df = pl.DataFrame(
        {
            "region_id": [1, 1],
            "year": [2020, 2024],
            "status": [0.5, 0.7],
        }
    )
    result = calculate_trend(df, trend_years=[2020, 2021, 2022, 2023, 2024])
    assert result["dimension"].to_list() == ["trend"]
