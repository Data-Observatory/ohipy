#!/usr/bin/env python3
"""Generate R fixtures for 44 parity tests."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / "comparative" / "cache"
FIXTURES_DIR = PROJECT_ROOT / "comparative" / "fixtures"
DATA_DIR = PROJECT_ROOT / "data"
SCENARIO_DIR = PROJECT_ROOT / "comparative" / "scenario_temp"
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


def prepare_scenario(dataset: str, variation: str) -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from tests.parity.data_modifiers import (
        modify_goal_weights,
        remove_pressure_from_matrix,
        remove_resilience_from_matrix,
    )

    if SCENARIO_DIR.exists():
        shutil.rmtree(SCENARIO_DIR)
    SCENARIO_DIR.mkdir(parents=True)

    conf_dir = SCENARIO_DIR / "conf"
    conf_dir.mkdir(parents=True)

    chl_conf = PROJECT_ROOT / "chl" / "comunas" / "conf"
    conf_files = [
        "goals.csv",
        "pressures_matrix.csv",
        "resilience_matrix.csv",
        "pressure_categories.csv",
        "resilience_categories.csv",
        "scenario_data_years.csv",
        "config.R",
        "functions.R",
    ]
    for f in conf_files:
        shutil.copy(chl_conf / f, conf_dir / f)
    shutil.copy(DATA_DIR / "layers.csv", SCENARIO_DIR / "layers.csv")

    layers_dir = SCENARIO_DIR / "layers"
    if dataset == "original":
        shutil.copytree(DATA_DIR / "layers" / "csv", layers_dir)
    else:
        noise_name = f"{dataset}_seed42"
        shutil.copytree(CACHE_DIR / noise_name / "layers" / "csv", layers_dir)

    if variation in WEIGHT_MODS:
        modify_goal_weights(conf_dir / "goals.csv", conf_dir / "goals.csv", WEIGHT_MODS[variation])
    elif variation == "pressure_cw_conquimica":
        remove_pressure_from_matrix(
            conf_dir / "pressures_matrix.csv", conf_dir / "pressures_matrix.csv", ["cw_conquimica"]
        )
    elif variation == "pressure_des_habitat_marino":
        remove_pressure_from_matrix(
            conf_dir / "pressures_matrix.csv",
            conf_dir / "pressures_matrix.csv",
            ["des_habitat_marino"],
        )
    elif variation == "pressure_both":
        remove_pressure_from_matrix(
            conf_dir / "pressures_matrix.csv", conf_dir / "pressures_matrix.csv", PRESSURE_COLUMNS
        )
    elif variation == "resilience_areas_mp":
        remove_resilience_from_matrix(
            conf_dir / "resilience_matrix.csv", conf_dir / "resilience_matrix.csv", ["areas_mp"]
        )
    elif variation == "resilience_cum_n_tratamiento":
        remove_resilience_from_matrix(
            conf_dir / "resilience_matrix.csv",
            conf_dir / "resilience_matrix.csv",
            ["cum_n_tratamiento"],
        )
    elif variation == "resilience_both":
        remove_resilience_from_matrix(
            conf_dir / "resilience_matrix.csv",
            conf_dir / "resilience_matrix.csv",
            RESILIENCE_COLUMNS,
        )


def run_r_calculation(output_csv: Path) -> bool:
    r_script = """
setwd("/home/project/comparative/scenario_temp")
library(ohicore)
library(plyr)
library(dplyr)
conf <- ohicore::Conf("conf")
layers <- ohicore::Layers("layers.csv", "layers")
layers$data$scenario_year <- 2024
scores <- ohicore::CalculateAll(conf, layers)
write.csv(scores, "/home/project/comparative/scenario_temp/scores.csv", na = "NA", row.names = FALSE)
"""

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
        print(f"    R stderr: {result.stderr[:500]}")
        return False

    temp_scores = SCENARIO_DIR / "scores.csv"
    if temp_scores.exists():
        shutil.copy(temp_scores, output_csv)
        return True
    return False


def generate_fixture(dataset: str, variation: str, overwrite: bool = False) -> bool:
    fixture_path = FIXTURES_DIR / dataset / f"{variation}.csv"
    if fixture_path.exists() and not overwrite:
        print(f"  ✓ {dataset}/{variation} exists")
        return True

    fixture_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        prepare_scenario(dataset, variation)
        success = run_r_calculation(fixture_path)
        if success:
            print(f"  ✓ {dataset}/{variation}")
        return success
    except Exception as e:
        print(f"  ✗ {dataset}/{variation}: {e}")
        return False


def generate_all_fixtures(
    datasets: list[str], variations: list[str], overwrite: bool = False
) -> tuple[int, int]:
    success, failures = 0, 0
    for ds in datasets:
        for var in variations:
            if generate_fixture(ds, var, overwrite):
                success += 1
            else:
                failures += 1
    return success, failures


def check_fixtures() -> int:
    missing = []
    for ds in DATASETS:
        for var in VARIATIONS:
            if not (FIXTURES_DIR / ds / f"{var}.csv").exists():
                missing.append(f"{ds}/{var}")
    if missing:
        print(f"Missing {len(missing)} fixtures:")
        for m in missing:
            print(f"  - {m}")
        return 1
    print(f"✓ All {len(DATASETS) * len(VARIATIONS)} fixtures exist")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate R fixtures")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--generate-noise-only", action="store_true")
    parser.add_argument("--datasets", nargs="+", choices=DATASETS, default=DATASETS)
    parser.add_argument("--variations", nargs="+", choices=VARIATIONS, default=VARIATIONS)
    args = parser.parse_args()

    if args.check:
        return check_fixtures()

    print("Generating noisy layers...")
    generate_noisy_layers(force=args.overwrite)

    if args.generate_noise_only:
        return 0

    total = len(args.datasets) * len(args.variations)
    print(f"\nGenerating {total} fixtures...")
    success, failures = generate_all_fixtures(args.datasets, args.variations, args.overwrite)
    print(f"\n✓ Complete: {success} generated, {failures} failed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
