"""Parity tests comparing R vs Python when removing pressures/resiliences.

6 variations (all using standard data/layers, no noise datasets):
- 2 individual pressure removals
- 2 individual resilience removals
- 2 combined pressure+resilience removals

Fixtures are pre-computed R outputs stored as CSVs. Tests run Python's
calculate_all() live with matching ConfigOverlay, then compare scores
within tolerance 0.01.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import polars as pl
import pytest

from tests.helpers.comparison import assert_parity, compare_scores

# =============================================================================
# CONSTANTS: Must match dimension_removal_fixtures.py
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = PROJECT_ROOT / "tests" / "comparative" / "fixtures" / "dimension_removal"

TOLERANCE = 0.01
AUTO_GEN = os.environ.get("OHI_AUTO_GENERATE_FIXTURES", "") == "1"

# 6 variations: 2 pressures, 2 resiliences, 2 combined
VARIATIONS: dict[str, dict[str, list[str]]] = {
    "pressure_cw_conquimica": {
        "pressures": ["cw_conquimica"],
        "resiliences": [],
    },
    "pressure_cc_anomaliast": {
        "pressures": ["cc_anomaliast"],
        "resiliences": [],
    },
    "resilience_species_diversity": {
        "pressures": [],
        "resiliences": ["species_diversity"],
    },
    "resilience_cum_n_tratamiento": {
        "pressures": [],
        "resiliences": ["cum_n_tratamiento"],
    },
    "combined_cw_conquimica_species_diversity": {
        "pressures": ["cw_conquimica"],
        "resiliences": ["species_diversity"],
    },
    "combined_cc_anomaliast_cum_n_tratamiento": {
        "pressures": ["cc_anomaliast"],
        "resiliences": ["cum_n_tratamiento"],
    },
}


# =============================================================================
# FIXTURE BOOTSTRAP (AUTO-GENERATION)
# =============================================================================


@pytest.fixture(scope="session", autouse=AUTO_GEN)
def bootstrap_fixtures() -> None:
    """Generate all R fixtures at session start when AUTO_GEN is enabled."""
    if not AUTO_GEN:
        return

    import subprocess

    result = subprocess.run(
        [sys.executable, "tests/parity/dimension_removal_fixtures.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.fail(
            f"Fixture generation failed with return code {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


# =============================================================================
# PARAMETRIZED TEST
# =============================================================================


@pytest.mark.dimension_removal
@pytest.mark.parametrize("variation", list(VARIATIONS.keys()))
def test_dimension_removal_parity(variation: str) -> None:
    """Test Python vs R parity for dimension removal variations.

    This test:
    1. Checks if R fixture exists (skips if not)
    2. Applies same dimension removal via ConfigOverlay
    3. Runs Python calculation with default data/ paths
    4. Loads R fixture CSV
    5. Compares within tolerance (0.01)
    """
    fixture_path = FIXTURES_DIR / f"{variation}.csv"

    # Skip if fixture doesn't exist and AUTO_GEN is false
    if not fixture_path.exists() and not AUTO_GEN:
        pytest.skip(
            f"R fixture not found: {fixture_path}\n"
            f"Run: uv run python tests/parity/dimension_removal_fixtures.py"
        )

    # If AUTO_GEN is true and fixture still missing, fail fast
    if not fixture_path.exists():
        pytest.fail(
            f"R fixture not found and AUTO_GEN is enabled: {fixture_path}\n"
            f"Fixture generation may have failed. "
            f"Run: uv run python tests/parity/dimension_removal_fixtures.py"
        )

    from typing import cast

    from ohipy.calculate_all import calculate_all
    from ohipy.config import load_config
    from ohipy.config_overlay import ConfigOverlay
    from ohipy.layers import load_layers
    from ohipy.types import ConfigData, DisableOverride

    config: ConfigData = load_config()

    overlay = ConfigOverlay()
    disable = cast(DisableOverride, cast(object, VARIATIONS[variation]))
    config = overlay.apply_all(config, {"disable": disable})

    # Load layers and calculate
    layers = load_layers(config)
    py_scores = calculate_all(config, layers)

    # Load R fixture
    r_scores = pl.read_csv(fixture_path)

    # Drop null/NaN score rows to match R fixture key set
    py_scores = py_scores.filter(pl.col("score").is_not_null() & ~pl.col("score").is_nan())
    r_scores = r_scores.filter(pl.col("score").is_not_null() & ~pl.col("score").is_nan())

    # Compare
    result = compare_scores(py_scores, r_scores, tolerance=TOLERANCE)

    if result.failure_count > 0:
        assert_parity(result, dataset="dimension_removal", variation=variation)
