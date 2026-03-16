"""Data modification utilities for parity testing.

Provides functions to inject noise, modify weights, and modify
pressure/resilience matrices for comprehensive R vs Python testing.
"""

import random
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl


def inject_noise_to_layers(
    source_dir: Path,
    target_dir: Path,
    sigma_pct: float = 0.05,
    seed: int = 42,
    columns_to_skip: set[str] | None = None,
) -> None:
    """Inject Gaussian noise into numeric layer columns.

    Args:
        source_dir: Directory containing original layer CSV files
        target_dir: Directory to write modified layer files
        sigma_pct: Noise level as percentage of column std (0.05 = 5%)
        seed: Random seed for reproducibility
        columns_to_skip: Column names to exclude from noise injection
    """
    random.seed(seed)
    np.random.seed(seed)

    if columns_to_skip is None:
        columns_to_skip = {
            "region_id",
            "rgn_id",
            "year",
            "MACROZONA",
            "taxon_name",
            "habitat",
            "category",
            "layer",
        }

    target_dir.mkdir(parents=True, exist_ok=True)

    for csv_file in source_dir.glob("*.csv"):
        try:
            df = pl.read_csv(csv_file, null_values=["NA", "N/A", ""])
        except Exception:
            shutil.copy(csv_file, target_dir / csv_file.name)
            continue

        # Find numeric columns to modify
        numeric_cols = [
            col
            for col in df.columns
            if df[col].dtype in (pl.Float64, pl.Float32, pl.Int64, pl.Int32)
            and col not in columns_to_skip
        ]

        if not numeric_cols:
            # Just copy file as-is if no numeric columns
            shutil.copy(csv_file, target_dir / csv_file.name)
            continue

        # Inject noise
        modifications = {}
        for col in numeric_cols:
            col_data = df[col].to_numpy()
            # Calculate std, handling potential NaN values
            valid_mask = ~np.isnan(col_data) & ~np.isinf(col_data)
            if valid_mask.sum() > 1:
                col_std = float(np.std(col_data[valid_mask]))
            else:
                col_std = 1.0

            if col_std == 0:
                col_std = 1.0

            noise = np.random.normal(0, sigma_pct * col_std, size=len(col_data))
            # Only add noise to valid (non-NaN) values
            noisy_data = col_data.copy()
            noisy_data[valid_mask] = col_data[valid_mask] + noise[valid_mask]
            modifications[col] = noisy_data

        df = df.with_columns(
            [pl.Series(col, vals).alias(col) for col, vals in modifications.items()]
        )

        df.write_csv(target_dir / csv_file.name)


def modify_goal_weights(
    source_goals: Path,
    target_goals: Path,
    weight_mods: dict[str, float],
) -> None:
    """Modify goal weights in goals.csv.

    Args:
        source_goals: Path to original goals.csv
        target_goals: Path to write modified goals.csv
        weight_mods: Dict mapping goal codes to new weight multipliers
    """
    df = pl.read_csv(source_goals)

    # Apply weight modifications
    for goal, multiplier in weight_mods.items():
        # Find rows for this goal
        mask = df["goal"] == goal
        if mask.any():
            current_weights = df["weight"].to_numpy()
            new_weights = np.where(
                df["goal"].to_numpy() == goal,
                current_weights * multiplier,
                current_weights,
            )
            df = df.with_columns(pl.Series("weight", new_weights).alias("weight"))

    target_goals.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(target_goals)


def remove_pressure_from_matrix(
    source_matrix: Path,
    target_matrix: Path,
    pressures_to_remove: list[str],
) -> None:
    """Remove specified pressures from the pressure matrix.

    Args:
        source_matrix: Path to original pressures_matrix.csv
        target_matrix: Path to write modified matrix
        pressures_to_remove: List of pressure column names to remove
    """
    df = pl.read_csv(source_matrix)

    # Drop specified pressure columns
    cols_to_keep = [col for col in df.columns if col not in pressures_to_remove]
    df = df.select(cols_to_keep)

    target_matrix.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(target_matrix)


def remove_resilience_from_matrix(
    source_matrix: Path,
    target_matrix: Path,
    resiliences_to_remove: list[str],
) -> None:
    """Remove specified resilience measures from the resilience matrix.

    Args:
        source_matrix: Path to original resilience_matrix.csv
        target_matrix: Path to write modified matrix
        resiliences_to_remove: List of resilience column names to remove
    """
    df = pl.read_csv(source_matrix)

    # Drop specified resilience columns
    cols_to_keep = [col for col in df.columns if col not in resiliences_to_remove]
    df = df.select(cols_to_keep)

    target_matrix.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(target_matrix)


def get_numeric_columns(df: pl.DataFrame) -> list[str]:
    """Get list of numeric column names from a DataFrame."""
    return [
        col for col in df.columns if df[col].dtype in (pl.Float64, pl.Float32, pl.Int64, pl.Int32)
    ]
