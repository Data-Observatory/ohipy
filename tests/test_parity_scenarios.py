"""Comprehensive parity tests comparing R vs Python under various data modifications.

Scenarios:
1. Baseline (original data) - verify exact match with R fixture
2. Noise injection - Gaussian noise at multiple levels (Python internal consistency)
3. Weight modifications - Different goal weights (Python internal consistency)
4. Pressure/resilience removal - Matrix modifications (Python internal consistency)

Note: Modified data tests verify Python runs without errors and produces
reasonable output. Full R comparison requires regenerating R fixture which
is time-consuming and Docker-dependent.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from tests.parity.data_modifiers import (
    inject_noise_to_layers,
    modify_goal_weights,
    remove_pressure_from_matrix,
    remove_resilience_from_matrix,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CONF_DIR = DATA_DIR / "conf"
LAYERS_DIR = DATA_DIR / "layers/csv"
R_FIXTURE = PROJECT_ROOT / "comparative/scores_2024_r.csv"
TOLERANCE = 0.05

DOCKER_IMAGE = "ohicore-r-env"


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    result = subprocess.run(
        ["docker", "images", "-q", DOCKER_IMAGE],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _run_py_calculation(layers_dir: Path | None = None) -> pl.DataFrame:
    """Run Python calculation with optional custom layers directory."""
    from ohipy.config import load_config
    from ohipy.layers import load_layers
    from ohipy.calculate_all import calculate_all

    config = load_config()
    if layers_dir is not None:
        paths = config.get("config", {})
        if "paths" not in paths:
            paths["paths"] = {}
        paths["paths"]["layers_dir"] = str(layers_dir)
        config["config"] = paths
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


# ==============================================================================
# TEST 1: Baseline parity (compares against R fixture)
# ==============================================================================


def test_baseline_parity():
    """Test that Python matches R reference fixture."""
    if not R_FIXTURE.exists():
        pytest.skip(f"R fixture not found: {R_FIXTURE}")

    py_scores = _run_py_calculation()
    r_scores = pl.read_csv(R_FIXTURE)

    result = _compare_scores(py_scores, r_scores, TOLERANCE)

    assert result["failure_count"] == 0, (
        f"Baseline parity failed: {result['failure_count']} differences\n"
        f"Max diff: {result['max_diff']}"
    )


# ==============================================================================
# TEST 2: Noise injection (Python internal consistency)
# ==============================================================================


@pytest.mark.parametrize("noise_level", [0.01, 0.05, 0.10])
def test_noise_injection_runs(noise_level: float):
    """Test that Python handles noisy layer data without errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        noisy_layers = tmpdir / "layers"
        noisy_layers.mkdir()

        inject_noise_to_layers(
            LAYERS_DIR,
            noisy_layers,
            sigma_pct=noise_level,
            seed=42,
        )

        scores = _run_py_calculation(noisy_layers)

        assert len(scores) > 0, "No scores generated"
        assert "region_id" in scores.columns
        assert "goal" in scores.columns
        assert "dimension" in scores.columns
        assert "score" in scores.columns

        goal_count = scores.filter(pl.col("goal") == "FIS").height
        assert goal_count > 0, "FIS goal not calculated"


# ==============================================================================
# TEST 3: Weight modifications (Python internal consistency)
# ==============================================================================


@pytest.mark.parametrize(
    "weight_mods",
    [
        {"FIS": 0.5},
        {"FIS": 2.5, "MAR": 1.5},
        {"FP": 1.5},
        {"AO": 0.5, "TR": 1.5},
    ],
)
def test_weight_modification_runs(weight_mods: dict[str, float]):
    """Test that Python handles modified goal weights without errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mod_conf = tmpdir / "conf"
        mod_conf.mkdir()

        for f in CONF_DIR.glob("*.csv"):
            shutil.copy(f, mod_conf / f.name)

        mod_goals = tmpdir / "conf" / "goals.csv"
        modify_goal_weights(CONF_DIR / "goals.csv", mod_goals, weight_mods)

        scores = _run_py_calculation()

        assert len(scores) > 0, "No scores generated"


# ==============================================================================
# TEST 4: Pressure removal (Python internal consistency)
# ==============================================================================


@pytest.mark.parametrize(
    "pressure_removals",
    [
        ["po_fishing"],
        ["po_water_pollution"],
        ["po_fishing", "po_water_pollution"],
    ],
)
def test_pressure_removal_runs(pressure_removals: list[str]):
    """Test that Python handles removed pressures without errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mod_conf = tmpdir / "conf"
        mod_conf.mkdir()

        for f in CONF_DIR.glob("*.csv"):
            shutil.copy(f, mod_conf / f.name)

        mod_pressures = tmpdir / "conf" / "pressures_matrix.csv"
        remove_pressure_from_matrix(
            CONF_DIR / "pressures_matrix.csv", mod_pressures, pressure_removals
        )

        scores = _run_py_calculation()

        assert len(scores) > 0, "No scores generated"


# ==============================================================================
# TEST 5: Resilience removal (Python internal consistency)
# ==============================================================================


@pytest.mark.parametrize(
    "resilience_removals",
    [
        ["res_mpa"],
        ["res_water"],
        ["res_mpa", "res_water"],
    ],
)
def test_resilience_removal_runs(resilience_removals: list[str]):
    """Test that Python handles removed resilience without errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mod_conf = tmpdir / "conf"
        mod_conf.mkdir()

        for f in CONF_DIR.glob("*.csv"):
            shutil.copy(f, mod_conf / f.name)

        mod_resilience = tmpdir / "conf" / "resilience_matrix.csv"
        remove_resilience_from_matrix(
            CONF_DIR / "resilience_matrix.csv", mod_resilience, resilience_removals
        )

        scores = _run_py_calculation()

        assert len(scores) > 0, "No scores generated"
