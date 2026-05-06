"""OHIPipeline - Simplified one-call interface for OHI calculations."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from ohipy.calculate_all import calculate_all
from ohipy.config import load_config
from ohipy.config_overlay import ConfigOverlay
from ohipy.layers import load_layers
from ohipy.types import OverridesConfig


class OHIPipeline:
    """One-call interface for OHI calculations with parameter overrides.

    Provides a simple API for running OHI calculations with configurable
    year, data path, goal weights, and dimension toggles.

    Example:
        >>> # Default: run with production data
        >>> pipeline = OHIPipeline()
        >>> scores = pipeline.run(year=2024)

        >>> # Custom dataset
        >>> pipeline = OHIPipeline("simulations/scenario_a")
        >>> scores = pipeline.run(year=2023, weights={"FIS": 0.5, "MAR": 0.5})

        >>> # Skip pressures/resilience
        >>> scores = pipeline.run(skip_pressures=True, skip_resilience=True)
    """

    def __init__(
        self, data_path: str | Path = ".", layers_csv: str | Path | None = None
    ) -> None:
        """Initialize pipeline with data directory.

        Args:
            data_path: Base path for resolving all relative paths from config.yaml.
                The config.yaml paths (e.g. "data/conf/goals.csv") are resolved
                relative to this directory. Defaults to "." (current/project root).
                For a custom dataset at "simulations/scenario_a/", pass that path
                and ensure its config.yaml paths point correctly within it.
            layers_csv: Optional path to a custom layers.csv metadata file.
                When provided, overrides the default layers.csv from config.yaml.
                Useful when layer filenames differ from those declared in the
                default layers.csv (e.g. custom datasets with different naming).
        """
        self.data_path = Path(data_path)
        self.layers_csv = layers_csv
        self._overlay = ConfigOverlay()

    def run(
        self,
        year: int = 2024,
        weights: dict[str, float] | None = None,
        disable: list[str] | None = None,
        skip_pressures: bool = False,
        skip_resilience: bool = False,
    ) -> pl.DataFrame:
        """Run full OHI calculation with parameter overrides.

        Args:
            year: Scenario year for the calculation. Affects which data years
                are used via scenario_data_years.csv mapping.
            weights: Optional dict mapping goal codes (e.g., "FIS", "MAR") to
                weight values. Weights are normalized to sum to 1.
            disable: Optional list of pressure/resilience column names to
                remove from the pressure and resilience matrices.
            skip_pressures: If True, use neutral pressure values (0.0) instead
                of computing them.
            skip_resilience: If True, use neutral resilience values (100.0)
                instead of computing them.

        Returns:
            DataFrame with columns: goal, dimension, region_id, score.
            Dimensions include: status, trend, pressures, resilience, future,
            score, Index.
        """
        config = load_config(
            data_path=self.data_path, year=year, layers_csv=self.layers_csv
        )
        layers = load_layers(config)

        overrides: OverridesConfig = {}
        if weights is not None:
            overrides["weights"] = weights
        if disable is not None:
            overrides["disable"] = {"pressures": disable, "resiliences": disable}

        if overrides:
            config = self._overlay.apply_all(config, overrides)

        return calculate_all(
            config,
            layers,
            skip_pressures=skip_pressures,
            skip_resilience=skip_resilience,
        )


__all__ = ["OHIPipeline"]
