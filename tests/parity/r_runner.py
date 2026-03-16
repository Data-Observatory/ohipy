"""R calculation runner via Docker.

Provides functions to run the R ohicore calculation with custom
configuration and layer directories.
"""

import shutil
import subprocess
from pathlib import Path

import polars as pl

DOCKER_IMAGE = "ohicore-r-env"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def docker_available() -> bool:
    """Check if Docker and the R image are available."""
    if not shutil.which("docker"):
        return False
    result = subprocess.run(
        ["docker", "images", "-q", DOCKER_IMAGE],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def run_r_calculation(
    conf_dir: Path,
    layers_dir: Path,
    output_csv: Path | None = None,
) -> pl.DataFrame | None:
    """Run R calculation via Docker and return scores.

    Args:
        conf_dir: Path to configuration directory
        layers_dir: Path to layers directory
        output_csv: Optional path to save scores CSV

    Returns:
        Polars DataFrame with scores, or None if Docker not available
    """
    if not docker_available():
        return None

    if output_csv is None:
        output_csv = conf_dir / "scores.csv"

    # Build the R script
    r_script = f'''
# R calculation script with custom paths
library(dplyr)

# Source functions from chl repository
source("/home/project/chl/comunas/conf/config.R", encoding = "UTF-8")
source("/home/project/chl/comunas/conf/functions.R", encoding = "UTF-8")

# Load layers
layers <- list()
layers_meta <- read.csv("{conf_dir}/../layers.csv")

for (i in 1:nrow(layers_meta)) {{
  layer_file <- file.path("{layers_dir}", layers_meta$layer[i])
  if (file.exists(layer_file)) {{
    layers$data[[layers_meta$layer[i]]] <- read.csv(layer_file)
  }}
}}

# Override conf paths
conf <- list()
conf$config <- list()
conf$config$years <- list()

# Load goals configuration
goals <- read.csv("{conf_dir}/goals.csv")
conf$goals <- goals

# Load matrices
conf$pressure_matrix <- read.csv("{conf_dir}/pressures_matrix.csv")
conf$resilience_matrix <- read.csv("{conf_dir}/resilience_matrix.csv")

# Run calculation
scores <- CalculateAll(layers, conf)

# Write output
write.csv(scores, "{output_csv}", row.names = FALSE)
'''

    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{PROJECT_ROOT}:/home/project",
            "-w",
            "/home/project",
            DOCKER_IMAGE,
            "Rscript",
            "-e",
            r_script,
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"R calculation failed (exit {result.returncode})\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    return pl.read_csv(output_csv)


def run_r_with_temporary_data(
    conf_dir: Path,
    layers_dir: Path,
) -> pl.DataFrame | None:
    """Run R calculation and return scores DataFrame.

    Convenience wrapper that handles temp output file.
    """
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        output_path = Path(f.name)

    try:
        result = run_r_calculation(conf_dir, layers_dir, output_path)
        return result
    finally:
        if output_path.exists():
            output_path.unlink()
