"""ConfigOverlay system for applying overrides to OHI configuration."""

from __future__ import annotations

import copy
from typing import cast

import polars as pl

from .types import ConfigData, DisableOverride, MatricesOverride, OverridesConfig


class ConfigOverlay:
    """Apply overrides to OHI configuration.

    Override precedence: disable > matrices (weights is INDEPENDENT)

    This means:
    1. If both disable and matrices are provided, matrices are applied first,
       then disable takes precedence (removes columns even from custom matrices)
    2. Weights is independent - it affects the goals DataFrame, not matrices
    """

    def apply_weights(self, config: ConfigData, weights: dict[str, float]) -> ConfigData:
        """Apply weight overrides to goals.

        Normalizes all goal weights so the total sums to 1.

        Args:
            config: Configuration dictionary with 'goals' DataFrame
            weights: Dictionary mapping goal codes to weight values

        Returns:
            New config dictionary with updated goal weights
        """
        new_config = copy.deepcopy(config)
        goals_df = cast(pl.DataFrame, new_config["goals"]).clone()

        # Update weights for specified goals
        for goal, weight in weights.items():
            goals_df = goals_df.with_columns(
                pl.when(pl.col("goal") == goal)
                .then(pl.lit(weight))
                .otherwise(pl.col("weight"))
                .alias("weight")
            )

        total = cast(float, goals_df.select(pl.col("weight").sum()).item())
        if total > 0:
            goals_df = goals_df.with_columns((pl.col("weight") / total).alias("weight"))

        new_config["goals"] = goals_df
        return new_config

    def apply_disable(self, config: ConfigData, disable: DisableOverride) -> ConfigData:
        """Remove disabled pressure/resilience columns from matrices.

        Args:
            config: Configuration dictionary with pressure/resilience matrices
            disable: Dictionary with 'pressures' and/or 'resiliences' lists

        Returns:
            New config dictionary with columns removed from matrices
        """
        new_config = copy.deepcopy(config)

        pressures_to_disable = disable.get("pressures", [])
        resiliences_to_disable = disable.get("resiliences", [])

        if pressures_to_disable:
            pm = cast(pl.DataFrame, new_config["pressures_matrix"]).clone()
            cols_to_keep = [c for c in pm.columns if c not in pressures_to_disable]
            new_config["pressures_matrix"] = pm.select(cols_to_keep)

        if resiliences_to_disable:
            rm = cast(pl.DataFrame, new_config["resilience_matrix"]).clone()
            cols_to_keep = [c for c in rm.columns if c not in resiliences_to_disable]
            new_config["resilience_matrix"] = rm.select(cols_to_keep)

        return new_config

    def apply_matrices(self, config: ConfigData, matrices: MatricesOverride) -> ConfigData:
        """Replace pressure/resilience matrices with custom ones.

        Args:
            config: Configuration dictionary
            matrices: Dictionary with 'pressures' and/or 'resilience' DataFrames

        Returns:
            New config dictionary with replaced matrices
        """
        new_config = copy.deepcopy(config)

        if "pressures" in matrices:
            new_config["pressures_matrix"] = matrices["pressures"].clone()
        if "resilience" in matrices:
            new_config["resilience_matrix"] = matrices["resilience"].clone()

        return new_config

    def apply_all(self, config: ConfigData, overrides: OverridesConfig) -> ConfigData:
        """Apply all overrides. Order: disable > matrices (weights independent).

        Precedence:
        1. First apply matrices (if provided)
        2. Then apply disable (takes precedence over matrices - removes columns)
        3. Weights is independent - applied separately

        Args:
            config: Configuration dictionary
            overrides: Dictionary with 'weights', 'disable', and/or 'matrices'

        Returns:
            New config dictionary with all overrides applied
        """
        result = config

        # First apply matrices (if provided)
        if "matrices" in overrides and overrides["matrices"]:
            result = self.apply_matrices(result, overrides["matrices"])

        # Then apply disable (takes precedence over matrices)
        if "disable" in overrides and overrides["disable"]:
            result = self.apply_disable(result, overrides["disable"])

        # Weights is independent - applied separately
        if "weights" in overrides and overrides["weights"]:
            result = self.apply_weights(result, overrides["weights"])

        return result


__all__ = ["ConfigOverlay"]
