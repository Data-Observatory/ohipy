"""Tests for OHIPipeline class."""

from typing import cast

import polars as pl
import pytest

from ohipy.pipeline import OHIPipeline


class TestOHIPipelineInit:
    """Test OHIPipeline initialization."""

    @pytest.mark.integrity
    def test_default_data_path(self):
        """Default data_path is '.' (project root)."""
        pipeline = OHIPipeline()
        assert str(pipeline.data_path) == "."

    @pytest.mark.integrity
    def test_custom_data_path(self):
        """Custom data_path is stored as Path."""
        pipeline = OHIPipeline("data")
        assert pipeline.data_path.name == "data"


class TestOHIPipelineRun:
    """Test OHIPipeline.run() with various parameters."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pipeline = OHIPipeline(".")

    @pytest.mark.integrity
    def test_default_run_produces_scores(self):
        """Default run produces a scores DataFrame with expected schema."""
        scores = self.pipeline.run()
        assert isinstance(scores, pl.DataFrame)
        assert set(scores.columns) == {"goal", "dimension", "region_id", "score"}
        assert scores.height > 0

    @pytest.mark.integrity
    def test_default_run_has_all_dimensions(self):
        """Default run includes all expected dimensions."""
        scores = self.pipeline.run()
        dimensions = set(scores["dimension"].unique().to_list())
        expected = {"status", "trend", "pressures", "resilience", "future", "score"}
        assert expected.issubset(dimensions), f"Missing dimensions: {expected - dimensions}"

    @pytest.mark.integrity
    def test_default_run_has_index(self):
        """Default run includes Index goal."""
        scores = self.pipeline.run()
        goals = scores["goal"].unique().to_list()
        assert "Index" in goals

    @pytest.mark.integrity
    def test_year_param_changes_scenario_year(self):
        """Different year should produce different results for multi-year layers."""
        scores_2024 = self.pipeline.run(year=2024)
        # Just verify it runs without error and produces output
        assert scores_2024.height > 0
        assert "score" in scores_2024.columns

    @pytest.mark.integrity
    def test_weights_override(self):
        """Weights override produces valid output."""
        scores = self.pipeline.run(weights={"FIS": 2.0, "MAR": 0.5})
        assert scores.height > 0
        # Index score should exist
        index_score = scores.filter((pl.col("goal") == "Index") & (pl.col("dimension") == "score"))
        assert index_score.height > 0

    @pytest.mark.integrity
    def test_skip_pressures(self):
        """Skip pressures produces output with neutral pressure values."""
        scores = self.pipeline.run(skip_pressures=True)
        pressures = scores.filter(pl.col("dimension") == "pressures")
        assert pressures.height > 0
        # All pressures should be 0.0
        assert (pressures["score"] == 0.0).all()

    @pytest.mark.integrity
    def test_skip_resilience(self):
        """Skip resilience produces output with neutral resilience values."""
        scores = self.pipeline.run(skip_resilience=True)
        resilience = scores.filter(pl.col("dimension") == "resilience")
        assert resilience.height > 0
        # All resilience should be 100.0
        assert (resilience["score"] == 100.0).all()

    @pytest.mark.integrity
    def test_skip_both_dimensions(self):
        """Skip both pressures and resilience produces valid output."""
        scores = self.pipeline.run(skip_pressures=True, skip_resilience=True)
        assert scores.height > 0
        # Should still have future and score dimensions
        dims = set(scores["dimension"].unique().to_list())
        assert "future" in dims
        assert "score" in dims

    @pytest.mark.integrity
    def test_disable_parameter(self):
        """Disable removes a pressure/resilience column and changes scores."""
        scores_default = self.pipeline.run()
        scores_disabled = self.pipeline.run(disable=["cw_conpatogenos"])

        # Produces valid output
        assert scores_disabled.height > 0
        assert set(scores_disabled.columns) == {"goal", "dimension", "region_id", "score"}

        # Pressures dimension still exists
        pressures = scores_disabled.filter(pl.col("dimension") == "pressures")
        assert pressures.height > 0

        # Scores differ from default (disabling a column changes pressure calculations)
        default_pressures = scores_default.filter(
            (pl.col("dimension") == "pressures") & (pl.col("goal") == "CW")
        ).sort("region_id")
        disabled_pressures = scores_disabled.filter(
            (pl.col("dimension") == "pressures") & (pl.col("goal") == "CW")
        ).sort("region_id")
        assert not default_pressures["score"].equals(disabled_pressures["score"]), (
            "Disabling cw_conpatogenos should change CW pressure scores"
        )

    @pytest.mark.integrity
    def test_disable_multiple_columns(self):
        """Disabling multiple pressure/resilience columns produces valid output."""
        scores = self.pipeline.run(disable=["cw_conpatogenos", "cw_connutrientesmar"])
        assert scores.height > 0
        assert set(scores.columns) == {"goal", "dimension", "region_id", "score"}
        # All dimensions still present
        dims = set(scores["dimension"].unique().to_list())
        assert "pressures" in dims
        assert "resilience" in dims
        assert "score" in dims

    @pytest.mark.integrity
    def test_weights_change_scores(self):
        """Extreme weights produce a different Index score than defaults."""
        scores_default = self.pipeline.run()
        scores_weighted = self.pipeline.run(weights={"FIS": 100.0, "MAR": 0.001})

        def _global_index(df: pl.DataFrame) -> float:
            row = df.filter(
                (pl.col("goal") == "Index")
                & (pl.col("dimension") == "score")
                & (pl.col("region_id") == 0)
            )
            assert row.height == 1
            return cast(float, row["score"].item())

        default_idx = _global_index(scores_default)
        weighted_idx = _global_index(scores_weighted)
        assert default_idx != weighted_idx, (
            f"Different weights should change Index score: default={default_idx}, weighted={weighted_idx}"
        )

    @pytest.mark.integrity
    def test_year_produces_different_status(self):
        """Different years produce different status scores for at least one region."""
        scores_2024 = self.pipeline.run(year=2024)
        scores_2021 = self.pipeline.run(year=2021)

        status_2024 = (
            scores_2024.filter(pl.col("dimension") == "status")
            .select("region_id", "goal", "score")
            .rename({"score": "score_2024"})
        )
        status_2021 = (
            scores_2021.filter(pl.col("dimension") == "status")
            .select("region_id", "goal", "score")
            .rename({"score": "score_2021"})
        )

        joined = status_2024.join(status_2021, on=["region_id", "goal"], how="inner")
        # Filter out rows where either score is null/nan
        valid = joined.filter(
            pl.col("score_2024").is_not_null()
            & ~pl.col("score_2024").is_nan()
            & pl.col("score_2021").is_not_null()
            & ~pl.col("score_2021").is_nan()
        )
        different = valid.filter(pl.col("score_2024") != pl.col("score_2021"))
        assert different.height > 0, (
            "At least one region should have different status between 2024 and 2021"
        )

    @pytest.mark.integrity
    def test_combined_params(self):
        """All parameters work together: year, weights, disable, no skips."""
        scores = self.pipeline.run(
            year=2023,
            weights={"FIS": 2.0},
            disable=["cw_conpatogenos"],
            skip_pressures=False,
            skip_resilience=False,
        )
        assert scores.height > 0
        assert set(scores.columns) == {"goal", "dimension", "region_id", "score"}
        dims = set(scores["dimension"].unique().to_list())
        for expected_dim in {"status", "trend", "pressures", "resilience", "future", "score"}:
            assert expected_dim in dims, f"Missing dimension: {expected_dim}"
        goals = scores["goal"].unique().to_list()
        assert "Index" in goals

    @pytest.mark.integrity
    def test_score_range_valid(self):
        """Non-null, non-NaN scores are in valid range (0-100 bounded, -1 to 1 trend)."""
        scores = self.pipeline.run()
        finite = pl.col("score").is_not_null() & ~pl.col("score").is_nan()

        bounded_dims = scores.filter(
            pl.col("dimension").is_in(["score", "status", "future", "pressures", "resilience"])
            & finite
        )
        if bounded_dims.height > 0:
            assert ((bounded_dims["score"] >= 0) & (bounded_dims["score"] <= 100)).all(), (
                "Scores outside 0-100 range found"
            )

        trend = scores.filter((pl.col("dimension") == "trend") & finite)
        if trend.height > 0:
            assert ((trend["score"] >= -1) & (trend["score"] <= 1)).all(), (
                "Trend scores outside -1 to 1 range found"
            )
