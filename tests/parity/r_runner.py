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
CHL_REPO_PATH = PROJECT_ROOT / "chl"


def docker_daemon_available() -> bool:
    """Check if Docker daemon is actually running.

    Returns:
        True if Docker daemon is available and accessible, False otherwise.
    """
    if not shutil.which("docker"):
        return False

    # Try to list containers to verify daemon is actually running
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result.returncode == 0


def docker_available() -> bool:
    """Check if Docker and the R image are available.

    This is a backward-compatible wrapper that checks:
    1. Docker binary exists
    2. Docker daemon is running
    3. R environment image is built

    Returns:
        True if all prerequisites are met, False otherwise.
    """
    if not docker_daemon_available():
        return False

    result = subprocess.run(
        ["docker", "images", "-q", DOCKER_IMAGE],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def build_docker_image() -> bool:
    """Build the R environment Docker image.

    Args:
        dockerfile_path: Path to the Dockerfile (default: comparative/images/R/Dockerfile)

    Returns:
        True if build succeeded, False otherwise.
    """
    dockerfile_path = PROJECT_ROOT / "tests" / "comparative" / "images" / "R" / "Dockerfile"

    build_context = str(dockerfile_path.parent)
    result = subprocess.run(
        ["docker", "build", "-t", DOCKER_IMAGE, build_context],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=600,  # 10 minute build timeout
    )

    if result.returncode != 0:
        print(f"Docker build failed:\n{result.stderr}")
        return False

    return True


def ensure_docker_image() -> bool:
    """Ensure the R environment Docker image exists and is built.

    This function:
    1. Checks if the image already exists (via docker_available)
    2. If not, builds it automatically
    3. Returns True only if image exists after this operation

    Returns:
        True if image exists or was successfully built, False otherwise.
    """
    if docker_available():
        return True

    # Try to build the image if it doesn't exist
    return build_docker_image()


def check_chl_repo() -> bool:
    """Check if the chl repository is present and valid.

    Returns:
        True if chl repository exists and contains required files, False otherwise.
    """
    if not CHL_REPO_PATH.exists():
        print(f"Error: chl repository not found at {CHL_REPO_PATH}")
        return False

    # Check for required R source files
    required_files = [
        CHL_REPO_PATH / "comunas" / "conf" / "config.R",
        CHL_REPO_PATH / "comunas" / "conf" / "functions.R",
    ]

    for filepath in required_files:
        if not filepath.exists():
            print(f"Error: Required chl file not found: {filepath}")
            return False

    return True


def run_r_calculation(
    conf_dir: Path,
    layers_dir: Path,
    output_csv: Path | None = None,
) -> pl.DataFrame | None:
    """Run R calculation via Docker and return scores.

    This function performs comprehensive prerequisite checks before execution:
    1. Verifies Docker daemon is running
    2. Ensures the R environment image exists (builds if needed)
    3. Checks chl repository is present
    4. Executes R calculation with host UID:GID for file permissions
    5. Includes 300s timeout and detailed error reporting

    Args:
        conf_dir: Path to configuration directory
        layers_dir: Path to layers directory
        output_csv: Optional path to save scores CSV

    Returns:
        Polars DataFrame with scores, or None if any prerequisite check fails.
    """
    # Check prerequisites and return None if any fail (safe failure)
    if not docker_daemon_available():
        print("Error: Docker daemon is not available. Please ensure Docker is running.")
        return None

    if not ensure_docker_image():
        print("Error: Docker image build failed or does not exist.")
        return None

    if not check_chl_repo():
        print("Error: chl repository is missing required files.")
        return None

    if output_csv is None:
        output_csv = conf_dir / "scores.csv"

    # Get host UID and GID for file permissions
    host_uid = subprocess.run(
        ["id", "-u"],
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout.strip()
    host_gid = subprocess.run(
        ["id", "-g"],
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout.strip()

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

    # Execute Docker command with host UID:GID and timeout
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{PROJECT_ROOT}:/home/project",
        "-w",
        "/home/project",
        "-u",
        f"{host_uid}:{host_gid}",
        DOCKER_IMAGE,
        "Rscript",
        "-e",
        r_script,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=300,  # 5 minute execution timeout
    )

    if result.returncode != 0:
        # Format error message with command, exit code, and stderr tail
        stderr_tail = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
        error_msg = (
            f"R calculation failed (exit {result.returncode})\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {stderr_tail}"
        )
        raise RuntimeError(error_msg)

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
