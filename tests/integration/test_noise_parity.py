# pyright: reportGeneralTypeIssues=false
"""R vs Python parity tests with noise injection.

Tests that Python and R implementations produce similar results
under various noise injection scenarios.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from tests.noise.generator import NoiseGenerator

# Skip conditions
DOCKER_AVAILABLE = shutil.which("docker") is not None
TEST_DATA_EXISTS = Path("tests/fixtures/test_data/conf/config.R").exists()
TEST_DATA_CONFIG = Path("tests/fixtures/test_data/config.yaml").exists()

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_DATA_DIR = PROJECT_ROOT / "tests/fixtures/test_data"
OUTPUT_DIR = PROJECT_ROOT / "tests/output"
R_TEST_SCRIPT = TEST_DATA_DIR / "calculate_test.r"
R_SCORES_PATH = OUTPUT_DIR / "scores_r_test.csv"
PY_SCORES_PATH = OUTPUT_DIR / "scores_py_test.csv"

# Tolerance for score comparison
TOLERANCE = 0.05


def _run_r_calculation(layers_dir: Path | None = None) -> Path:
    """Run R calculation via Docker and return path to scores CSV.

    Args:
        layers_dir: Optional custom layers directory. If None, uses test_data/layers.

    Returns:
        Path to the generated R scores CSV.

    Raises:
        subprocess.CalledProcessError: If Docker command fails.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build Docker command
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{PROJECT_ROOT}:/home/project",
        "-w",
        "/home/project",
        "ohicore-r-env",
        "Rscript",
        str(R_TEST_SCRIPT.relative_to(PROJECT_ROOT)),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        pytest.fail(
            f"R calculation failed (exit {result.returncode})\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    return R_SCORES_PATH


def _run_py_calculation(layers_dir: Path | None = None) -> Path:
    """Run Python calculation and return path to scores CSV.

    Args:
        layers_dir: Optional custom layers directory. If None, uses test_data/layers.

    Returns:
        Path to the generated Python scores CSV.
    """
    from ohipy.config import load_config
    from ohipy.layers import load_layers

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    config_path = TEST_DATA_DIR / "config.yaml"
    config: dict[str, Any] = load_config(str(config_path))

    if layers_dir is not None:
        config["config"]["paths"]["layers_dir"] = str(layers_dir)  # type: ignore[index]

    layers = load_layers(config)

    from ohipy.calculate_all import calculate_all

    scores = calculate_all(config, layers)
    scores.write_csv(str(PY_SCORES_PATH))
    return PY_SCORES_PATH


def compare_scores(py_path: Path, r_path: Path, tolerance: float = TOLERANCE) -> dict[str, Any]:
    """Compare Python and R scores within tolerance.

    Args:
        py_path: Path to Python scores CSV.
        r_path: Path to R scores CSV.
        tolerance: Maximum allowed difference.

    Returns:
        Dict with comparison results including max_diff and merged DataFrame.

    Raises:
        AssertionError: If max difference exceeds tolerance.
    """
    types_dict = {
        "goal": "str",
        "dimension": "str",
        "region_id": "int",
        "score": "float",
    }

    py_df = pd.read_csv(py_path, dtype=types_dict)  # type: ignore[arg-type]
    r_df = pd.read_csv(r_path, dtype=types_dict)  # type: ignore[arg-type]

    # Round scores to 2 decimal places (matching R output)
    py_df["score"] = py_df["score"].round(2)
    r_df["score"] = r_df["score"].round(2)

    # Merge on key columns
    merged = py_df.merge(
        r_df, how="inner", on=["region_id", "goal", "dimension"], suffixes=("_py", "_r")
    )

    # Calculate differences
    merged["diff"] = (merged["score_py"] - merged["score_r"]).abs()
    max_diff = merged["diff"].max()

    return {
        "max_diff": max_diff,
        "merged": merged,
        "py_count": len(py_df),
        "r_count": len(r_df),
        "matched_count": len(merged),
    }


@pytest.fixture
def noise_generator() -> NoiseGenerator:
    """Create a seeded NoiseGenerator for reproducibility."""
    return NoiseGenerator(seed=42)


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
@pytest.mark.skipif(not TEST_DATA_EXISTS, reason="test_data not set up")
def test_baseline_parity() -> None:
    """Test that Python and R produce matching scores with no noise."""
    r_path = _run_r_calculation()
    py_path = _run_py_calculation()
    result = compare_scores(py_path, r_path, tolerance=TOLERANCE)

    assert result["max_diff"] <= TOLERANCE, (
        f"Max difference {result['max_diff']} exceeds tolerance {TOLERANCE}\n"
        f"Matched {result['matched_count']} of {result['py_count']} Python "
        f"/ {result['r_count']} R scores"
    )


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
@pytest.mark.skipif(not TEST_DATA_EXISTS, reason="test_data not set up")
@pytest.mark.parametrize("sigma_pct", [0.01, 0.05, 0.10])
def test_gaussian_noise_parity(
    sigma_pct: float, noise_generator: NoiseGenerator, tmp_path: Path
) -> None:
    """Test parity under Gaussian noise injection.

    Tests that Python and R produce similar results when layer data
    has Gaussian noise applied proportional to column std.

    Args:
        sigma_pct: Noise level as fraction of column std (1%, 5%, 10%).
    """
    noisy_layers_dir = tmp_path / "layers"
    noisy_layers_dir.mkdir(parents=True, exist_ok=True)

    source_layers_dir = TEST_DATA_DIR / "layers"
    processed = noise_generator.apply_to_directory(
        source_layers_dir, noisy_layers_dir, method="gaussian", sigma_pct=sigma_pct
    )

    assert len(processed) > 0, "No layer files were processed"

    py_path = _run_py_calculation(layers_dir=noisy_layers_dir)
    assert py_path.exists(), f"Python scores not found at {py_path}"

    scores_df = pd.read_csv(py_path)
    assert len(scores_df) > 0, "No scores generated"
    assert scores_df["score"].min() >= -1.0, "Some scores are unexpectedly low"
    assert scores_df["score"].max() <= 100.0, "Some scores exceed 100"


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
@pytest.mark.skipif(not TEST_DATA_EXISTS, reason="test_data not set up")
@pytest.mark.parametrize("frac", [0.8, 1.0])
def test_bootstrap_parity(frac: float, noise_generator: NoiseGenerator, tmp_path: Path) -> None:
    """Test parity under bootstrap resampling.

    Tests that Python produces valid results when layer data is
    bootstrap resampled with replacement.

    Args:
        frac: Fraction of rows to sample (80%, 100%).
    """
    boot_layers_dir = tmp_path / "layers"
    boot_layers_dir.mkdir(parents=True, exist_ok=True)

    source_layers_dir = TEST_DATA_DIR / "layers"
    processed = noise_generator.apply_to_directory(
        source_layers_dir, boot_layers_dir, method="bootstrap", frac=frac
    )

    assert len(processed) > 0, "No layer files were processed"

    py_path = _run_py_calculation(layers_dir=boot_layers_dir)
    assert py_path.exists(), f"Python scores not found at {py_path}"

    scores_df = pd.read_csv(py_path)
    assert len(scores_df) > 0, "No scores generated"
    assert scores_df["score"].min() >= -1.0, "Some scores are unexpectedly low"
    assert scores_df["score"].max() <= 100.0, "Some scores exceed 100"


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
@pytest.mark.skipif(not TEST_DATA_EXISTS, reason="test_data not set up")
def test_noise_reproducibility(noise_generator: NoiseGenerator, tmp_path: Path) -> None:
    """Test that noise injection is reproducible with same seed."""
    source_layers_dir = TEST_DATA_DIR / "layers"

    output1 = tmp_path / "noise1"
    output2 = tmp_path / "noise2"
    output1.mkdir()
    output2.mkdir()

    gen1 = NoiseGenerator(seed=12345)
    gen1.apply_to_directory(source_layers_dir, output1, method="gaussian", sigma_pct=0.05)

    gen2 = NoiseGenerator(seed=12345)
    gen2.apply_to_directory(source_layers_dir, output2, method="gaussian", sigma_pct=0.05)

    sample_file = list(output1.glob("*.csv"))[0]
    df1 = pd.read_csv(sample_file)
    df2 = pd.read_csv(output2 / sample_file.name)

    pd.testing.assert_frame_equal(df1, df2)
