"""Noise injection utilities for robustness testing of OHI calculations.

This module provides tools to inject various types of noise into layer data
to test the robustness of OHI score calculations.
"""

# pyright: reportGeneralTypeIssues=false, reportUnknownMemberType=false

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# Columns that should never have noise applied (IDs, keys, categorical)
NON_NUMERIC_PATTERNS = {
    "rgn_id",
    "region_id",
    "year",
    "id_num",
    "goal",
    "dimension",
    "category",
    "layer",
    "filename",
    "targets",
    "name",
    "label",
    "code",
    "type",
    "especie",  # Species name column from fis_b_bmsy_chl2024.csv
}


def _is_numeric_column(col_name: str, df: pd.DataFrame) -> bool:
    """Check if a column should be treated as numeric for noise injection.

    Args:
        col_name: Name of the column
        df: DataFrame containing the column

    Returns:
        True if the column should have noise applied, False otherwise
    """
    col_name_lower = col_name.lower()

    # Check if column name matches non-numeric patterns
    for pattern in NON_NUMERIC_PATTERNS:
        if pattern in col_name_lower:
            return False

    # Check if the column dtype is numeric
    return pd.api.types.is_numeric_dtype(df[col_name])


def _get_numeric_columns(df: pd.DataFrame, columns: Optional[list[str]] = None) -> list[str]:
    """Get list of numeric columns eligible for noise injection.

    Args:
        df: DataFrame to analyze
        columns: Specific columns to filter (if None, auto-detect all numeric)

    Returns:
        List of column names that can have noise applied
    """
    if columns is None:
        # Auto-detect numeric columns
        return [col for col in df.columns if _is_numeric_column(col, df)]

    # Filter provided columns to only include valid numeric ones
    return [col for col in columns if col in df.columns and _is_numeric_column(col, df)]


class NoiseGenerator:
    """Injects noise into layer data for robustness testing.

    All methods use a seeded random number generator for reproducibility.
    Non-numeric columns (IDs, years, categories) are always preserved.

    Example:
        >>> gen = NoiseGenerator(seed=42)
        >>> df = pd.read_csv("layer.csv")
        >>> noisy = gen.inject_gaussian(df, sigma_pct=0.05)  # 5% noise
    """

    def __init__(self, seed: Optional[int] = None):
        """Initialize the noise generator.

        Args:
            seed: Random seed for reproducibility. If None, results will vary.
        """
        self.seed = seed
        self._rng = np.random.default_rng(seed)

    def _reset_rng(self, seed: Optional[int] = None) -> None:
        """Reset the random number generator.

        Args:
            seed: New seed to use. If None, uses the original seed.
        """
        self._rng = np.random.default_rng(seed if seed is not None else self.seed)

    def inject_gaussian(
        self,
        df: pd.DataFrame,
        columns: Optional[list[str]] = None,
        sigma_pct: float = 0.05,
    ) -> pd.DataFrame:
        """Add Gaussian noise to numeric columns.

        Noise is proportional to the standard deviation of each column:
        noise ~ N(0, sigma_pct * std(column))

        Args:
            df: Input DataFrame
            columns: Columns to apply noise to (None = all numeric)
            sigma_pct: Noise level as fraction of column std (default 5%)

        Returns:
            DataFrame with Gaussian noise added to specified columns

        Example:
            >>> gen = NoiseGenerator(seed=42)
            >>> noisy = gen.inject_gaussian(df, sigma_pct=0.10)  # 10% noise
        """
        # Handle edge cases
        if df.empty or len(df) == 0:
            return df.copy()

        result = df.copy()
        numeric_cols = _get_numeric_columns(result, columns)

        for col in numeric_cols:
            col_data = result[col]

            # Skip columns that are all NaN
            if col_data.isna().all():
                continue

            # Calculate noise scale based on column's standard deviation
            col_std = col_data.std()
            if pd.isna(col_std) or col_std == 0:
                # If std is 0 or NaN, use mean absolute deviation or a small default
                col_std = col_data.mad() if col_data.mad() > 0 else 0.01

            noise_scale = sigma_pct * col_std
            noise = self._rng.normal(0, noise_scale, size=len(result))

            # Add noise only to non-NaN values
            mask = ~col_data.isna()
            result.loc[mask, col] = col_data[mask] + noise[mask]

        return result

    def bootstrap_resample(
        self,
        df: pd.DataFrame,
        frac: float = 1.0,
        seed: Optional[int] = None,
    ) -> pd.DataFrame:
        """Resample rows with replacement (bootstrap).

        Args:
            df: Input DataFrame
            frac: Fraction of rows to sample (1.0 = same size)
            seed: Optional seed override for this operation

        Returns:
            Resampled DataFrame

        Example:
            >>> gen = NoiseGenerator(seed=42)
            >>> bootstrapped = gen.bootstrap_resample(df, frac=0.8)
        """
        # Handle edge cases
        if df.empty or len(df) == 0:
            return df.copy()

        if len(df) == 1:
            # Single row - just return copies
            n_samples = max(1, int(len(df) * frac))
            return pd.concat([df] * n_samples, ignore_index=True)

        # Use provided seed or reset to original
        rng = np.random.default_rng(seed if seed is not None else self.seed)
        n_samples = max(1, int(len(df) * frac))

        return df.sample(n=n_samples, replace=True, random_state=rng).reset_index(drop=True)

    def inject_dropout(
        self,
        df: pd.DataFrame,
        columns: Optional[list[str]] = None,
        rate: float = 0.1,
    ) -> pd.DataFrame:
        """Set random values to NaN (simulating missing data).

        Args:
            df: Input DataFrame
            columns: Columns to apply dropout to (None = all numeric)
            rate: Fraction of values to set to NaN (default 10%)

        Returns:
            DataFrame with random values set to NaN

        Example:
            >>> gen = NoiseGenerator(seed=42)
            >>> sparse = gen.inject_dropout(df, rate=0.2)  # 20% missing
        """
        # Handle edge cases
        if df.empty or len(df) == 0:
            return df.copy()

        result = df.copy()
        numeric_cols = _get_numeric_columns(result, columns)

        for col in numeric_cols:
            col_data = result[col]

            # Skip columns that are all NaN already
            if col_data.isna().all():
                continue

            # Get indices of non-NaN values
            non_nan_mask = ~col_data.isna()
            non_nan_indices = result.index[non_nan_mask].to_numpy()

            if len(non_nan_indices) == 0:
                continue

            # Calculate how many values to drop
            n_to_drop = max(1, int(len(non_nan_indices) * rate))
            n_to_drop = min(n_to_drop, len(non_nan_indices))

            # Randomly select indices to set to NaN
            drop_indices = self._rng.choice(non_nan_indices, size=n_to_drop, replace=False)
            result.loc[drop_indices, col] = np.nan

        return result

    def apply_to_directory(
        self,
        layers_dir: str | Path,
        output_dir: str | Path,
        method: str = "gaussian",
        **kwargs,
    ) -> dict[str, Path]:
        """Apply noise injection to all CSV files in a directory.

        Preserves the directory structure. Non-CSV files are copied unchanged.

        Args:
            layers_dir: Source directory containing CSV layer files
            output_dir: Destination directory for noisy files
            method: Noise method to use ("gaussian", "dropout", "bootstrap")
            **kwargs: Additional arguments passed to the noise method:
                - gaussian: sigma_pct (default 0.05)
                - dropout: rate (default 0.1)
                - bootstrap: frac (default 1.0), seed (optional)

        Returns:
            Dict mapping original filenames to output paths

        Raises:
            ValueError: If method is not recognized

        Example:
            >>> gen = NoiseGenerator(seed=42)
            >>> gen.apply_to_directory(
            ...     "data/layers/csv",
            ...     "data/layers_noisy",
            ...     method="gaussian",
            ...     sigma_pct=0.05
            ... )
        """
        layers_path = Path(layers_dir)
        output_path = Path(output_dir)

        # Create output directory
        output_path.mkdir(parents=True, exist_ok=True)

        # Map method names to functions
        method_map = {
            "gaussian": self.inject_gaussian,
            "dropout": self.inject_dropout,
            "bootstrap": self.bootstrap_resample,
        }

        if method not in method_map:
            raise ValueError(f"Unknown method '{method}'. Choose from: {list(method_map.keys())}")

        noise_func = method_map[method]
        processed_files = {}

        # Process all CSV files
        for csv_file in layers_path.glob("**/*.csv"):
            # Preserve relative directory structure
            relative_path = csv_file.relative_to(layers_path)
            output_file = output_path / relative_path

            # Create subdirectories if needed
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Load, apply noise, and save
            df = pd.read_csv(csv_file)
            noisy_df = noise_func(df, **kwargs)
            noisy_df.to_csv(output_file, index=False)

            processed_files[str(csv_file)] = output_file

        return processed_files


__all__ = ["NoiseGenerator"]
