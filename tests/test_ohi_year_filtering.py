"""Tests for _filter_by_ohi_year helper function."""

import polars as pl

from ohipy.layers import ROLLING_WINDOW_LAYERS, _filter_by_ohi_year


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


# ---------------------------------------------------------------------------
# Rolling-window layer exemption (Issue 1: ohi_year double-filtering / data loss)
# ---------------------------------------------------------------------------


def _rolling_window_layer_df() -> pl.DataFrame:
    """A rolling-window layer where R stamped ohi_year as a plain copy of year.

    This mirrors e.g. fis_meancatch: group_by(year, ...) then add_ohi_year(),
    so every row has ohi_year == year (one value per row, NOT a pre-computed
    per-scenario window).
    """
    years = [2020, 2021, 2022, 2023, 2024]
    return pl.DataFrame(
        {
            "rgn_id": [1] * 5,
            "year": years,
            "ohi_year": years,  # plain copy of year
            "catch": [10.0, 11.0, 12.0, 13.0, 14.0],
        }
    )


def test_rolling_window_layer_not_truncated() -> None:
    """A rolling-window layer with ohi_year==year must keep ALL years.

    Without the exemption, filtering ohi_year == scenario_year would collapse
    the layer to a single year and silently break the multi-year trend/window
    computation the goal function performs internally.
    """
    df = _rolling_window_layer_df()
    result = _filter_by_ohi_year(df, 2024, layer_name="fis_meancatch")
    assert result.shape[0] == 5
    assert result["year"].to_list() == [2020, 2021, 2022, 2023, 2024]


def test_rolling_window_exemption_covers_all_goal_layers() -> None:
    """Every rolling-window goal layer is exempted, regardless of scenario_year."""
    for layer_name in ROLLING_WINDOW_LAYERS:
        df = _rolling_window_layer_df()
        result = _filter_by_ohi_year(df, 2024, layer_name=layer_name)
        assert result.shape[0] == 5, f"{layer_name} was wrongly truncated"


def test_non_rolling_layer_still_filtered() -> None:
    """A non-exempt single-year layer (e.g. ico_status) is still filtered.

    ICO's goal function does NOT filter by year itself, so ohi_year filtering
    remains load-bearing to pick the scenario-year snapshot.
    """
    df = _rolling_window_layer_df()
    result = _filter_by_ohi_year(df, 2024, layer_name="ico_status")
    assert result.shape[0] == 1
    assert result["year"].to_list() == [2024]


def test_window_explosion_layers_are_not_exempt() -> None:
    """Bucket-A window-explosion layers MUST stay filtered (avoid dup years).

    np_harvest_tonnes_relative and tr_jobs_pct_tourism carry the full [x-4, x]
    window under each ohi_year=x tag, so the same `year` appears under multiple
    ohi_year values. They must be filtered to the scenario window, else the
    goal-function join on `year` would carry cross-window duplicate rows.
    """
    assert "np_harvest_tonnes_relative" not in ROLLING_WINDOW_LAYERS
    assert "tr_jobs_pct_tourism" not in ROLLING_WINDOW_LAYERS


def test_no_layer_name_preserves_backward_compat() -> None:
    """Omitting layer_name keeps the original filtering behavior."""
    df = _rolling_window_layer_df()
    result = _filter_by_ohi_year(df, 2024)
    assert result.shape[0] == 1
