# pyright: reportGeneralTypeIssues=false
"""OHIRunner - Main runner for OHI calculations with override support."""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, cast

import pandas as pd

if TYPE_CHECKING:
    import pandas as pd

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

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize runner with configuration.

        Args:
            config_path: Optional path to config.yaml. If None, uses default location.
        """
        self._config: dict[str, Any] = load_config(config_path)
        self._overlay: ConfigOverlay = ConfigOverlay()

    def run(
        self,
        year: int,
        layers: dict[str, pd.DataFrame],
        overrides: OverridesConfig | None = None,
    ) -> pd.DataFrame:
        """Run single year calculation.

        Args:
            year: Year for the calculation (used for layer selection).
            layers: Dictionary mapping layer names to DataFrames.
            overrides: Optional overrides configuration with:
                - weights: Dict mapping goal codes to weight values
                - disable: Dict with pressures/resiliences to disable
                - matrices: Custom pressure/resilience matrices

        Returns:
            DataFrame with columns: region_id, goal, dimension, score
        """
        # Deep copy config to avoid mutating the original
        config = copy.deepcopy(self._config)

        # Apply overrides if provided
        if overrides:
            config = self._overlay.apply_all(config, overrides)

        # Prepare layers dict in format expected by calculate_all
        layers_dict = {"data": layers, "meta": self._config["layers"]}

        # Run calculation
        scores = calculate_all(config, layers_dict)
        return scores

    def run_multi_year(
        self,
        years: list[int],
        layers: dict[str, pd.DataFrame],
        overrides: OverridesConfig | None = None,
        statistics: list[SUPPORTED_STATISTICS] | None = None,
    ) -> pd.DataFrame:
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
        all_scores: list[pd.DataFrame] = []
        for year in years:
            scores = self.run(year, layers, overrides)
            scores = scores.copy()
            scores["_year"] = year
            all_scores.append(scores)

        combined = pd.concat(all_scores, ignore_index=True)

        # Determine which statistics to compute
        stats_to_compute = statistics if statistics is not None else ALL_STATISTICS.copy()

        # Group by (goal, dimension, region_id) and compute statistics
        results: list[dict[str, Any]] = []
        for (goal, dim, rid), group in combined.groupby(["goal", "dimension", "region_id"]):
            acc = StatisticsAccumulator(stats_to_compute)
            acc.add(group["score"].tolist())
            stats = acc.compute()
            stats["goal"] = goal
            stats["dimension"] = dim
            stats["region_id"] = rid
            results.append(stats)

        result_df = pd.DataFrame(results)

        # Reorder columns: region_id, goal, dimension, then statistics
        col_order = ["region_id", "goal", "dimension"] + [
            s for s in stats_to_compute if s in result_df.columns
        ]
        return cast(pd.DataFrame, result_df[col_order])


__all__ = ["OHIRunner"]
