# pyright: reportGeneralTypeIssues=false
"""OHIRunner - Main runner for OHI calculations with override support."""

from __future__ import annotations

import copy
from typing import Any, cast

import polars as pl

from ohipy.calculate_all import calculate_all
from ohipy.config import load_config
from ohipy.config_overlay import ConfigOverlay
from ohipy.statistics import ALL_STATISTICS, SUPPORTED_STATISTICS, StatisticsAccumulator
from ohipy.types import OverridesConfig


class OHIRunner:
    """Main runner for OHI calculations with override support.

    Provides a clean API for running single-year OHI calculations with
    optional configuration overrides.

    Example:
        >>> runner = OHIRunner()
        >>> layers = {"layer1": df1, "layer2": df2}
        >>> scores = runner.run(year=2024, layers=layers)
    """

    def __init__(
        self,
        config_path: str | None = None,
        data_path: str | None = None,
    ) -> None:
        """Initialize runner with configuration.

        Args:
            config_path: Optional path to config.yaml. If None, uses default location.
            data_path: Optional base directory for resolving relative paths from
                config.yaml. When given, replaces the project root as the base for
                all CSV/layer paths.
        """
        self._config: dict[str, Any] = load_config(config_path, data_path=data_path)
        self._data_path: str | None = data_path
        self._overlay: ConfigOverlay = ConfigOverlay()

    def run(
        self,
        year: int,
        layers: dict[str, pl.DataFrame],
        overrides: OverridesConfig | None = None,
    ) -> pl.DataFrame:
        """Run single year calculation.

        Args:
            year: Scenario year — sets ``scenario_year`` in the config dict so
                goal functions that reference it receive the correct value.
            layers: Dictionary mapping layer names to DataFrames.
            overrides: Optional overrides configuration with:
                - weights: Dict mapping goal codes to weight values
                - disable: Dict with pressures/resiliences to disable
                - matrices: Custom pressure/resilience matrices

        Returns:
            DataFrame with columns: region_id, goal, dimension, score
        """
        config = copy.deepcopy(self._config)
        config["config"]["scenario_year"] = year

        if overrides:
            config = self._overlay.apply_all(config, overrides)

        layers_dict = {"data": layers, "meta": self._config["layers"]}

        scores = calculate_all(config, layers_dict)
        return cast(pl.DataFrame, scores)

    def run_multi_year(
        self,
        years: list[int],
        layers: dict[str, pl.DataFrame],
        overrides: OverridesConfig | None = None,
        statistics: list[SUPPORTED_STATISTICS] | None = None,
    ) -> pl.DataFrame:
        """Run calculation for multiple years and aggregate statistics.

        Args:
            years: List of years to run calculations for.
            layers: Dictionary mapping layer names to DataFrames.
            overrides: Optional overrides configuration.
            statistics: List of statistics to compute. If None, computes all 9.

        Returns:
            DataFrame with columns: region_id, goal, dimension, [statistics...]
        """
        # Collect all scores
        all_scores: list[pl.DataFrame] = []
        for year in years:
            scores = self.run(year, layers, overrides)
            scores = scores.clone()
            scores = scores.with_columns(pl.lit(year).alias("_year"))
            all_scores.append(scores)

        combined = pl.concat(all_scores)

        # Determine which statistics to compute
        stats_to_compute = statistics if statistics is not None else ALL_STATISTICS.copy()

        # Group by (goal, dimension, region_id) and compute statistics
        results: list[dict[str, Any]] = []
        for (goal, dim, rid), group in combined.group_by(["goal", "dimension", "region_id"]):
            acc = StatisticsAccumulator(stats_to_compute)
            acc.add(group["score"].to_list())
            stats = acc.compute()
            stats["goal"] = goal
            stats["dimension"] = dim
            stats["region_id"] = rid
            results.append(stats)

        result_df = pl.DataFrame(results)

        # Reorder columns: region_id, goal, dimension, then statistics
        col_order = ["region_id", "goal", "dimension"] + [
            s for s in stats_to_compute if s in result_df.columns
        ]
        return result_df.select(col_order)


__all__ = ["OHIRunner"]
