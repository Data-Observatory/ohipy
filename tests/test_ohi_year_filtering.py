"""Tests for _filter_by_ohi_year helper function."""

import polars as pl

from ohipy.layers import _filter_by_ohi_year


def test_ohi_year_filters_matching_rows() -> None:
    """Rows with matching ohi_year or NULL are kept."""
    df = pl.DataFrame({"rgn_id": [1, 2, 3, 4], "ohi_year": [2023, 2024, 2024, None]})
    result = _filter_by_ohi_year(df, 2024)
    assert result.shape[0] == 3


def test_ohi_year_no_column_no_filtering() -> None:
    """No ohi_year column means df is returned unchanged."""
    df = pl.DataFrame({"rgn_id": [1, 2, 3], "value": [10, 20, 30]})
    result = _filter_by_ohi_year(df, 2024)
    assert result.shape[0] == 3


def test_ohi_year_null_scenario_year_no_filtering() -> None:
    """None scenario_year means df is returned unchanged."""
    df = pl.DataFrame({"rgn_id": [1, 2], "ohi_year": [2023, 2024]})
    result = _filter_by_ohi_year(df, None)
    assert result.shape[0] == 2


def test_ohi_year_all_null_keeps_all() -> None:
    """All-NULL ohi_year keeps all rows (static layers)."""
    df = pl.DataFrame({"rgn_id": [1, 2, 3], "ohi_year": [None, None, None]})
    result = _filter_by_ohi_year(df, 2024)
    assert result.shape[0] == 3


def test_ohi_year_empty_after_filter() -> None:
    """No rows match the scenario year; result is empty."""
    df = pl.DataFrame({"rgn_id": [1, 2], "ohi_year": [2023, 2023]})
    result = _filter_by_ohi_year(df, 2024)
    assert result.shape[0] == 0


def test_ohi_year_preserves_year_column() -> None:
    """The regular 'year' column is NOT affected by ohi_year filtering."""
    df = pl.DataFrame({
        "rgn_id": [1, 2, 3],
        "year": [2020, 2024, 2024],
        "ohi_year": [2023, 2024, 2024],
    })
    result = _filter_by_ohi_year(df, 2024)
    assert result.shape[0] == 2
    assert result["year"].to_list() == [2024, 2024]


def test_ohi_year_integer_type() -> None:
    """Works correctly when ohi_year is Int64 (nullable integer)."""
    df = pl.DataFrame({
        "rgn_id": [1, 2, 3],
        "ohi_year": pl.Series([2023, 2024, None]).cast(pl.Int64),
    })
    result = _filter_by_ohi_year(df, 2024)
    assert result.shape[0] == 2
