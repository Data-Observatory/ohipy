#!/usr/bin/env python3
"""Generate R fixtures for 44 parity tests."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / "comparative" / "cache"
FIXTURES_DIR = PROJECT_ROOT / "comparative" / "fixtures"
DATA_DIR = PROJECT_ROOT / "data"
DOCKER_IMAGE = "ohicore-r-env"

DATASETS = ["original", "noise_1pct", "noise_5pct", "noise_10pct"]
NOISE_CONFIGS = {
    "noise_1pct_seed42": (0.01, 42),
    "noise_5pct_seed42": (0.05, 42),
    "noise_10pct_seed42": (0.10, 42),
}
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
PRESSURE_COLUMNS = ["cw_conquimica", "des_habitat_marino"]
RESILIENCE_COLUMNS = ["areas_mp", "cum_n_tratamiento"]
WEIGHT_MODS = {
    "weight_fis_0.5": {"FIS": 0.5},
    "weight_fis_2.5_mar_1.5": {"FIS": 2.5, "MAR": 1.5},
    "weight_fp_1.5": {"FP": 1.5},
    "weight_ao_0.5_tr_1.5": {"AO": 0.5, "TR": 1.5},
}


def generate_noisy_layers(force: bool = False) -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from tests.parity.data_modifiers import inject_noise_to_layers

    source_dir = DATA_DIR / "layers" / "csv"
    for noise_name, (sigma_pct, seed) in NOISE_CONFIGS.items():
        cache_path = CACHE_DIR / noise_name / "layers" / "csv"
        if cache_path.exists() and not force:
            print(f"  ✓ {noise_name} exists")
            continue
        inject_noise_to_layers(source_dir, cache_path, sigma_pct, seed)
        print(f"  ✓ {noise_name}")


def check_fixtures() -> int:
    missing = []
    for ds in DATASETS:
        for var in VARIATIONS:
            if not (FIXTURES_DIR / ds / f"{var}.csv").exists():
                missing.append(f"{ds}/{var}")
    if missing:
        print(f"Missing {len(missing)} fixtures")
        for m in missing[:10]:
            print(f"  - {m}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
        return 1
    print(f"✓ All {len(DATASETS) * len(VARIATIONS)} fixtures exist")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate R fixtures")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--generate-noise-only", action="store_true")
    args = parser.parse_args()

    if args.check:
        return check_fixtures()

    print("Generating noisy layers...")
    generate_noisy_layers(force=args.overwrite)

    if args.generate_noise_only:
        return 0

    print("\nTo generate R fixtures, run:")
    print(
        "  docker run --rm -v $PWD:/home/project -w /home/project ohicore-r-env Rscript comparative/calculate_scores.r"
    )
    print("\nThen copy comparative/scores_2024_r.csv to comparative/fixtures/original/baseline.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
