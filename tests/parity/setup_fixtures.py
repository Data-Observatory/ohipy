"""Setup test fixtures for parity testing.

Provides CLI interface for generating test fixtures with various data modifications.
Generates R reference scores for 44 combinations: 4 datasets × 11 variations.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / "comparative" / "cache"
FIXTURES_DIR = PROJECT_ROOT / "comparative" / "fixtures"
DATA_DIR = PROJECT_ROOT / "data"

# Docker configuration
DOCKER_IMAGE = "ohicore-r-env"

# =============================================================================
# CONSTANTS: 44 combinations (4 datasets × 11 variations)
# =============================================================================

DATASETS = [
    "original",
    "noise_1pct",
    "noise_5pct",
    "noise_10pct",
]

NOISE_CONFIGS: dict[str, tuple[float, int]] = {
    "noise_1pct_seed42": (0.01, 42),
    "noise_5pct_seed42": (0.05, 42),
    "noise_10pct_seed42": (0.10, 42),
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


@dataclass
class FixtureSpec:
    """Specification for a single fixture."""

    dataset: str
    variation: str

    @property
    def fixture_path(self) -> Path:
        """Path to the fixture CSV file."""
        return FIXTURES_DIR / self.dataset / f"{self.variation}.csv"

    @property
    def layers_dir(self) -> Path:
        """Path to layers directory for this dataset."""
        if self.dataset == "original":
            return DATA_DIR / "layers" / "csv"
        return CACHE_DIR / self.dataset / "layers" / "csv"


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


def generate_noisy_layers(
    source_dir: Path | None = None,
    force: bool = False,
) -> None:
    """Generate noisy layer files for parity testing.

    Creates directories under comparative/cache/ with noise-injected layer files.

    Args:
        source_dir: Path to source layer CSV files (default: data/layers/csv)
        force: Regenerate even if cache exists
    """
    from tests.parity.data_modifiers import inject_noise_to_layers

    if source_dir is None:
        source_dir = DATA_DIR / "layers" / "csv"

    for noise_name, (sigma_pct, seed) in NOISE_CONFIGS.items():
        cache_path = CACHE_DIR / noise_name / "layers" / "csv"

        if cache_path.exists() and not force:
            print(f"  ✓ {noise_name} already exists (use --overwrite to regenerate)")
            continue

        inject_noise_to_layers(source_dir, cache_path, sigma_pct, seed)
        print(f"  ✓ Generated {noise_name} (sigma={sigma_pct:.0%}, seed={seed})")


def verify_r_runner() -> bool:
    """Verify R runner is available.

    Returns:
        True if Docker and R image are available, False otherwise
    """
    if not docker_available():
        print("✗ Docker not available or R image not found")
        print("  Build with: docker build -t ohicore-r-env comparative/images/R/")
        return False
    print("✓ Docker and R image available")
    return True


def _run_r_for_fixture(
    spec: FixtureSpec,
    temp_conf_dir: Path,
    output_csv: Path,
) -> None:
    """Run R calculation for a single fixture.

    Args:
        spec: Fixture specification
        temp_conf_dir: Temporary config directory
        output_csv: Output path for scores CSV
    """
    # Build R script
    r_script = f'''
library(dplyr)

# Source functions from chl repository
source("/home/project/chl/comunas/conf/config.R", encoding = "UTF-8")
source("/home/project/chl/comunas/conf/functions.R", encoding = "UTF-8")

# Load layers metadata
layers_meta <- read.csv("{temp_conf_dir.parent}/layers.csv")

# Load layers
layers <- list()
for (i in 1:nrow(layers_meta)) {{
  layer_file <- file.path("{spec.layers_dir}", layers_meta$layer[i])
  if (file.exists(layer_file)) {{
    layers$data[[layers_meta$layer[i]]] <- read.csv(layer_file)
  }}
}}

# Build config
conf <- list()
conf$config <- list()
conf$config$years <- list()

# Load goals
conf$goals <- read.csv("{temp_conf_dir}/goals.csv")

# Load matrices
conf$pressure_matrix <- read.csv("{temp_conf_dir}/pressures_matrix.csv")
conf$resilience_matrix <- read.csv("{temp_conf_dir}/resilience_matrix.csv")

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
            f"R calculation failed for {spec.dataset}/{spec.variation}:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


def _prepare_config_for_variation(
    spec: FixtureSpec,
    temp_conf_dir: Path,
) -> None:
    """Prepare configuration files for a specific variation.

    Args:
        spec: Fixture specification
        temp_conf_dir: Temporary directory to write config files
    """
    from tests.parity.data_modifiers import (
        modify_goal_weights,
        remove_pressure_from_matrix,
        remove_resilience_from_matrix,
    )

    temp_conf_dir.mkdir(parents=True, exist_ok=True)

    # Copy base config files
    source_conf = DATA_DIR / "conf"
    for config_file in ["goals.csv", "pressures_matrix.csv", "resilience_matrix.csv"]:
        shutil.copy(source_conf / config_file, temp_conf_dir / config_file)

    # Apply variation modifications
    variation = spec.variation

    if variation == "baseline":
        # No modifications needed
        pass

    elif variation in WEIGHT_MODS:
        modify_goal_weights(
            source_goals=temp_conf_dir / "goals.csv",
            target_goals=temp_conf_dir / "goals.csv",
            weight_mods=WEIGHT_MODS[variation],
        )

    elif variation == "pressure_cw_conquimica":
        remove_pressure_from_matrix(
            source_matrix=temp_conf_dir / "pressures_matrix.csv",
            target_matrix=temp_conf_dir / "pressures_matrix.csv",
            pressures_to_remove=["cw_conquimica"],
        )

    elif variation == "pressure_des_habitat_marino":
        remove_pressure_from_matrix(
            source_matrix=temp_conf_dir / "pressures_matrix.csv",
            target_matrix=temp_conf_dir / "pressures_matrix.csv",
            pressures_to_remove=["des_habitat_marino"],
        )

    elif variation == "pressure_both":
        remove_pressure_from_matrix(
            source_matrix=temp_conf_dir / "pressures_matrix.csv",
            target_matrix=temp_conf_dir / "pressures_matrix.csv",
            pressures_to_remove=PRESSURE_COLUMNS,
        )

    elif variation == "resilience_areas_mp":
        remove_resilience_from_matrix(
            source_matrix=temp_conf_dir / "resilience_matrix.csv",
            target_matrix=temp_conf_dir / "resilience_matrix.csv",
            resiliences_to_remove=["areas_mp"],
        )

    elif variation == "resilience_cum_n_tratamiento":
        remove_resilience_from_matrix(
            source_matrix=temp_conf_dir / "resilience_matrix.csv",
            target_matrix=temp_conf_dir / "resilience_matrix.csv",
            resiliences_to_remove=["cum_n_tratamiento"],
        )

    elif variation == "resilience_both":
        remove_resilience_from_matrix(
            source_matrix=temp_conf_dir / "resilience_matrix.csv",
            target_matrix=temp_conf_dir / "resilience_matrix.csv",
            resiliences_to_remove=RESILIENCE_COLUMNS,
        )

    # Copy layers.csv to parent directory
    shutil.copy(DATA_DIR / "layers.csv", temp_conf_dir.parent / "layers.csv")


def generate_single_fixture(spec: FixtureSpec, overwrite: bool = False) -> bool:
    """Generate a single fixture file.

    Args:
        spec: Fixture specification
        overwrite: Force regeneration even if exists

    Returns:
        True if successful, False otherwise
    """
    # Check if fixture already exists
    if spec.fixture_path.exists() and not overwrite:
        return True  # Already exists, skip

    # Ensure parent directory exists
    spec.fixture_path.parent.mkdir(parents=True, exist_ok=True)

    # Create temporary directory for config
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_conf_dir = Path(temp_dir) / "conf"

        try:
            # Prepare config files with modifications
            _prepare_config_for_variation(spec, temp_conf_dir)

            # Run R calculation
            _run_r_for_fixture(spec, temp_conf_dir, spec.fixture_path)

            return True

        except Exception as e:
            print(f"  ✗ Failed to generate {spec.dataset}/{spec.variation}: {e}")
            return False


def generate_all_fixtures(
    datasets: list[str] | None = None,
    variations: list[str] | None = None,
    overwrite: bool = False,
    parallel: int = 1,
) -> tuple[int, int]:
    """Generate all fixture files.

    Args:
        datasets: Datasets to generate (default: all)
        variations: Variations to generate (default: all)
        overwrite: Force regeneration
        parallel: Number of parallel processes (1 = sequential)

    Returns:
        Tuple of (success_count, failure_count)
    """
    if datasets is None:
        datasets = DATASETS
    if variations is None:
        variations = VARIATIONS

    # Build list of specs to generate
    specs = [FixtureSpec(ds, var) for ds in datasets for var in variations]

    # Check for existing fixtures if not overwriting
    if not overwrite:
        existing = [s for s in specs if s.fixture_path.exists()]
        to_generate = [s for s in specs if not s.fixture_path.exists()]
        if existing:
            print(f"  {len(existing)} fixtures already exist (use --overwrite to regenerate)")
        if not to_generate:
            print("  All fixtures already exist!")
            return len(specs), 0
        specs = to_generate

    success = 0
    failures = 0

    if parallel > 1:
        # Parallel execution
        print(f"  Running {len(specs)} fixtures with {parallel} parallel processes...")
        with ProcessPoolExecutor(max_workers=parallel) as executor:
            futures = {
                executor.submit(generate_single_fixture, spec, overwrite): spec for spec in specs
            }
            for future in as_completed(futures):
                spec = futures[future]
                try:
                    if future.result():
                        success += 1
                        print(f"  ✓ {spec.dataset}/{spec.variation}")
                    else:
                        failures += 1
                except Exception as e:
                    failures += 1
                    print(f"  ✗ {spec.dataset}/{spec.variation}: {e}")
    else:
        # Sequential execution
        for spec in specs:
            try:
                if generate_single_fixture(spec, overwrite):
                    success += 1
                    print(f"  ✓ {spec.dataset}/{spec.variation}")
                else:
                    failures += 1
            except Exception as e:
                failures += 1
                print(f"  ✗ {spec.dataset}/{spec.variation}: {e}")

    return success, failures


def check_fixtures(
    datasets: list[str] | None = None,
    variations: list[str] | None = None,
) -> int:
    """Check if all fixtures exist.

    Args:
        datasets: Datasets to check (default: all)
        variations: Variations to check (default: all)

    Returns:
        0 if all fixtures exist, 1 if any are missing
    """
    if datasets is None:
        datasets = DATASETS
    if variations is None:
        variations = VARIATIONS

    missing = []
    for ds in datasets:
        for var in variations:
            spec = FixtureSpec(ds, var)
            if not spec.fixture_path.exists():
                missing.append(spec)

    if missing:
        print(f"Missing {len(missing)} fixtures:")
        for spec in missing:
            print(f"  ✗ {spec.dataset}/{spec.variation}")
        return 1

    total = len(datasets) * len(variations)
    print(f"✓ All {total} fixtures exist")
    return 0


def list_combinations(
    datasets: list[str] | None = None,
    variations: list[str] | None = None,
) -> None:
    """List all dataset-variation combinations."""
    if datasets is None:
        datasets = DATASETS
    if variations is None:
        variations = VARIATIONS

    total = len(datasets) * len(variations)
    print(f"Available combinations: {total} total")
    print(f"  Datasets ({len(datasets)}): {', '.join(datasets)}")
    print(f"  Variations ({len(variations)}): {', '.join(variations)}")

    print("\nAll combinations:")
    for ds in datasets:
        for var in variations:
            spec = FixtureSpec(ds, var)
            exists = "✓" if spec.fixture_path.exists() else "✗"
            print(f"  {exists} {ds}/{var}")


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="Setup test fixtures for OHI parity testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all 44 combinations with status
  uv run python tests/parity/setup_fixtures.py --list

  # Check if all fixtures exist (exit 0 if OK, 1 if missing)
  uv run python tests/parity/setup_fixtures.py --check

  # Generate all missing fixtures
  uv run python tests/parity/setup_fixtures.py

  # Force regenerate all fixtures
  uv run python tests/parity/setup_fixtures.py --overwrite

  # Generate with 4 parallel R processes
  uv run python tests/parity/setup_fixtures.py --parallel 4

  # Generate specific dataset only
  uv run python tests/parity/setup_fixtures.py --datasets noise_1pct

  # Generate specific variations only
  uv run python tests/parity/setup_fixtures.py --variations baseline weight_fis_0.5
        """,
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all dataset-variation combinations with status",
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if all fixtures exist (exit 0 if OK, 1 if missing)",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Force regenerate existing fixtures",
    )

    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        metavar="N",
        help="Run N R processes in parallel (default: 1, sequential)",
    )

    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=DATASETS,
        default=DATASETS,
        help="Datasets to process (default: all)",
    )

    parser.add_argument(
        "--variations",
        nargs="+",
        choices=VARIATIONS,
        default=VARIATIONS,
        help="Variations to process (default: all)",
    )

    parser.add_argument(
        "--generate-noise-only",
        action="store_true",
        help="Only generate noisy layer files, don't run R",
    )

    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # List mode
    if args.list:
        list_combinations(args.datasets, args.variations)
        return 0

    # Check mode
    if args.check:
        return check_fixtures(args.datasets, args.variations)

    # Generate noise only mode
    if args.generate_noise_only:
        print("Generating noisy layer files...")
        generate_noisy_layers(force=args.overwrite)
        return 0

    # Verify R runner
    print("Verifying R runner...")
    if not verify_r_runner():
        return 1

    # Generate noisy layers first
    print("\nGenerating noisy layer files...")
    generate_noisy_layers(force=args.overwrite)

    # Generate fixtures
    total = len(args.datasets) * len(args.variations)
    print(f"\nGenerating {total} fixtures...")
    success, failures = generate_all_fixtures(
        datasets=args.datasets,
        variations=args.variations,
        overwrite=args.overwrite,
        parallel=args.parallel,
    )

    print(f"\n✓ Complete: {success} generated, {failures} failed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
