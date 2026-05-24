"""Tests for OHIPipeline.run_years()."""

import polars as pl
import pytest

from ohipy.pipeline import OHIPipeline


@pytest.fixture
def pipeline():
    return OHIPipeline()  # uses default data path (project root)


def test_run_years_single_year(pipeline):
    result = pipeline.run_years(years=[2024])
    assert "ohi_year" in result.columns
    assert result["ohi_year"].dtype == pl.Int16
    assert (result["ohi_year"] == 2024).all()
    assert result["score"].is_nan().sum() == 0
    assert result["score"].is_null().sum() == 0


def test_run_years_multiple_years(pipeline):
    result = pipeline.run_years(years=[2023, 2024])
    assert set(result["ohi_year"].unique().to_list()) == {2023, 2024}
    assert "goal" in result.columns
    assert "dimension" in result.columns
    assert "region_id" in result.columns
    assert "score" in result.columns


def test_run_years_stacks_correctly(pipeline):
    single_2023 = pipeline.run_years(years=[2023])
    single_2024 = pipeline.run_years(years=[2024])
    combined = pipeline.run_years(years=[2023, 2024])
    assert len(combined) == len(single_2023) + len(single_2024)


def test_run_years_empty_list(pipeline):
    result = pipeline.run_years(years=[])
    assert len(result) == 0
    assert "ohi_year" in result.columns


def test_run_years_ohi_year_is_int16(pipeline):
    result = pipeline.run_years(years=[2024])
    assert result["ohi_year"].dtype == pl.Int16
