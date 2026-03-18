"""Comprehensive parity tests comparing R vs Python across 44 combinations.

44 tests: 4 datasets × 11 variations

Datasets:
- original: uses data/layers/csv/
- noise_1pct: 1% Gaussian noise (seed=42)
- noise_5pct: 5% Gaussian noise (seed=42)
- noise_10pct: 10% Gaussian noise (seed=42)

Variations (11 per dataset):
- baseline: no modification
- weight_fis_0.5: FIS weight × 0.5
- weight_fis_2.5_mar_1.5: FIS × 2.5, MAR × 1.5
- weight_fp_1.5: FP × 1.5
- weight_ao_0.5_tr_1.5: AO × 0.5, TR × 1.5
- pressure_cw_conquimica: remove cw_conquimica pressure
- pressure_des_habitat_marino: remove des_habitat_marino pressure
- pressure_both: remove both pressures above
- resilience_areas_mp: remove areas_mp resilience
- resilience_cum_n_tratamiento: remove cum_n_tratamiento resilience
- resilience_both: remove both resiliences above
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, cast

import polars as pl
import pytest

# =============================================================================
# CONSTANTS: Must match setup_fixtures.py
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "comparative" / "cache"
FIXTURES_DIR = PROJECT_ROOT / "comparative" / "fixtures"
DATA_DIR = PROJECT_ROOT / "data"
CONF_DIR = DATA_DIR / "conf"
LAYERS_DIR = DATA_DIR / "layers" / "csv"

TOLERANCE = 0.05

# 4 datasets
DATASETS = [
    "original",
    "noise_1pct",
    "noise_5pct",
    "noise_10pct",
]

# Noise configs: (sigma_pct, seed)
NOISE_CONFIGS: dict[str, tuple[float, int]] = {
    "noise_1pct": (0.01, 42),
    "noise_5pct": (0.05, 42),
    "noise_10pct": (0.10, 42),
}

# 11 variations per dataset
VARIATIONS = [
    "baseline",
    "weight_fis_0.5",
    "weight_fis_2.5_mar_1.5",
    "weight_fp_1.5",
    "weight_ao_0.5_tr_1.5",
    "pressure_cw_conquimica",
    "pressure_des_habitat_marino",
    "pressure_both",
    "resilience_areas_mp",
    "resilience_cum_n_tratamiento",
    "resilience_both",
]

# Pressure column names (verified from data/conf/pressures_matrix.csv)
PRESSURE_COLUMNS = ["cw_conquimica", "des_habitat_marino"]

# Resilience column names (verified from data/conf/resilience_matrix.csv)
RESILIENCE_COLUMNS = ["areas_mp", "cum_n_tratamiento"]

# Weight modification specs
WEIGHT_MODS: dict[str, dict[str, float]] = {
    "weight_fis_0.5": {"FIS": 0.5},
    "weight_fis_2.5_mar_1.5": {"FIS": 2.5, "MAR": 1.5},
    "weight_fp_1.5": {"FP": 1.5},
    "weight_ao_0.5_tr_1.5": {"AO": 0.5, "TR": 1.5},
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _get_fixture_path(dataset: str, variation: str) -> Path:
    """Get path to R fixture CSV file."""
    return FIXTURES_DIR / dataset / f"{variation}.csv"


def _get_layers_dir(dataset: str) -> Path:
    """Get layers directory for a dataset."""
    if dataset == "original":
        return LAYERS_DIR
    # Use pre-cached noisy layers (with seed42 suffix)
    return CACHE_DIR / f"{dataset}_seed42" / "layers" / "csv"


def _run_py_calculation(
    layers_dir: Path | None = None,
    variation: str | None = None,
) -> pl.DataFrame:
    """Run Python calculation with optional custom paths and variations."""
    from ohipy.calculate_all import calculate_all
    from ohipy.config import load_config
    from ohipy.config_overlay import ConfigOverlay, OverridesConfig
    from ohipy.layers import load_layers
    from ohipy.types import ConfigData

    config: ConfigData = load_config()

    # Apply variation modifications via ConfigOverlay
    if variation is not None and variation != "baseline":
        overlay = ConfigOverlay()
        overrides: OverridesConfig = {}

        if variation in WEIGHT_MODS:
            overrides["weights"] = WEIGHT_MODS[variation]
        elif variation == "pressure_cw_conquimica":
            overrides["disable"] = {"pressures": ["cw_conquimica"]}
        elif variation == "pressure_des_habitat_marino":
            overrides["disable"] = {"pressures": ["des_habitat_marino"]}
        elif variation == "pressure_both":
            overrides["disable"] = {"pressures": PRESSURE_COLUMNS}
        elif variation == "resilience_areas_mp":
            overrides["disable"] = {"resiliences": ["areas_mp"]}
        elif variation == "resilience_cum_n_tratamiento":
            overrides["disable"] = {"resiliences": ["cum_n_tratamiento"]}
        elif variation == "resilience_both":
            overrides["disable"] = {"resiliences": RESILIENCE_COLUMNS}

        if overrides:
            config = overlay.apply_all(config, overrides)

    # Override layers path if provided
    if layers_dir is not None:
        paths_dict: dict[str, Any] = cast(dict[str, Any], config["config"])
        if "paths" not in paths_dict:
            paths_dict["paths"] = {}
        paths_dict["paths"]["layers_dir"] = str(layers_dir)

    layers = load_layers(config)
    scores = calculate_all(config, layers)
    return scores


def _compare_scores(
    py_scores: pl.DataFrame, r_scores: pl.DataFrame, tolerance: float
) -> dict[str, Any]:
    """Compare Python and R scores, return differences."""
    py_df = py_scores.with_columns(pl.col("score").round(2))
    r_df = r_scores.with_columns(pl.col("score").round(2))

    merged = py_df.join(
        r_df,
        on=["region_id", "goal", "dimension"],
        suffix="_r",
    )

    merged = merged.with_columns((pl.col("score") - pl.col("score_r")).abs().alias("diff"))

    nan_failures = merged.filter(pl.col("score").is_nan() & ~pl.col("score_r").is_nan())
    value_failures = merged.filter(
        ~pl.col("score").is_nan() & ~pl.col("score_r").is_nan() & (pl.col("diff") > tolerance)
    )

    failures = pl.concat([nan_failures, value_failures])

    return {
        "max_diff": merged["diff"].max() if len(merged) > 0 else 0,
        "failures": failures,
        "failure_count": len(failures),
        "py_count": len(py_scores),
        "r_count": len(r_scores),
    }


# =============================================================================
# FIXTURE EXISTENCE CHECK
# =============================================================================


def _all_fixtures_exist() -> bool:
    """Check if all 44 R fixtures exist."""
    for dataset in DATASETS:
        for variation in VARIATIONS:
            if not _get_fixture_path(dataset, variation).exists():
                return False
    return True


def _missing_fixtures() -> list[str]:
    """Return list of missing fixtures."""
    missing = []
    for dataset in DATASETS:
        for variation in VARIATIONS:
            if not _get_fixture_path(dataset, variation).exists():
                missing.append(f"{dataset}/{variation}")
    return missing


# =============================================================================
# PARAMETRIZED TEST
# =============================================================================


@pytest.mark.parametrize("dataset", DATASETS)
@pytest.mark.parametrize("variation", VARIATIONS)
def test_parity_full(dataset: str, variation: str) -> None:
    """Test Python vs R parity for all 44 combinations.

    This test:
    1. Checks if R fixture exists (skips if not)
    2. Applies same modification as R fixture
    3. Runs Python calculation
    4. Loads R fixture CSV
    5. Compares within tolerance (0.05)
    """
    fixture_path = _get_fixture_path(dataset, variation)

    # Skip if fixture doesn't exist
    if not fixture_path.exists():
        missing = _missing_fixtures()
        missing_str = ", ".join(missing[:5])
        if len(missing) > 5:
            missing_str += f", ... ({len(missing)} total)"
        pytest.skip(
            f"R fixture not found: {fixture_path}\n"
            f"Missing {len(missing)} fixtures: {missing_str}\n"
            f"Run: uv run python tests/parity/setup_fixtures.py"
        )

    # Create temp directories for modified data
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Use pre-cached layers (original or noisy)
        layers_dir = _get_layers_dir(dataset)

        # Run Python calculation
        py_scores = _run_py_calculation(layers_dir=layers_dir, variation=variation)

        # Load R fixture
        r_scores = pl.read_csv(fixture_path)

        # Compare
        result = _compare_scores(py_scores, r_scores, TOLERANCE)

        # Assert
        assert result["failure_count"] == 0, (
            f"Parity failed for {dataset}/{variation}: {result['failure_count']} differences\n"
            f"Max diff: {result['max_diff']}\n"
            f"Python scores: {result['py_count']}, R scores: {result['r_count']}"
        )
