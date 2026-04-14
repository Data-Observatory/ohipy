#!/usr/bin/env python3
"""Generate R fixtures for 6 dimension-removal parity test variations."""

import argparse
import fcntl
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = PROJECT_ROOT / "tests" / "comparative" / "fixtures" / "dimension_removal"
LOCKFILE = FIXTURES_DIR / ".lock"
DATA_DIR = PROJECT_ROOT / "data"
SCENARIO_DIR = PROJECT_ROOT / "tests" / "comparative" / "scenario_temp"
DOCKER_IMAGE = "ohicore-r-env"

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

CONF_FILES = [
    "goals.csv",
    "pressures_matrix.csv",
    "resilience_matrix.csv",
    "pressure_categories.csv",
    "resilience_categories.csv",
    "scenario_data_years.csv",
    "config.R",
    "functions.R",
]


@contextmanager
def acquire_lock() -> Iterator[None]:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    with LOCKFILE.open("a") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another process holds the fixture lock")
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def prepare_scenario(variation: str) -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from tests.parity.data_modifiers import (
        remove_pressure_from_matrix,
        remove_resilience_from_matrix,
    )

    if SCENARIO_DIR.exists():
        shutil.rmtree(SCENARIO_DIR)
    SCENARIO_DIR.mkdir(parents=True)

    conf_dir = SCENARIO_DIR / "conf"
    conf_dir.mkdir(parents=True)

    chl_conf = PROJECT_ROOT / "chl" / "comunas" / "conf"
    for f in CONF_FILES:
        shutil.copy(chl_conf / f, conf_dir / f)

    shutil.copy(DATA_DIR / "layers.csv", SCENARIO_DIR / "layers.csv")
    shutil.copytree(DATA_DIR / "layers" / "csv", SCENARIO_DIR / "layers")

    spec = VARIATIONS[variation]
    if spec["pressures"]:
        remove_pressure_from_matrix(
            conf_dir / "pressures_matrix.csv",
            conf_dir / "pressures_matrix.csv",
            spec["pressures"],
        )
    if spec["resiliences"]:
        remove_resilience_from_matrix(
            conf_dir / "resilience_matrix.csv",
            conf_dir / "resilience_matrix.csv",
            spec["resiliences"],
        )


def run_r_calculation(output_csv: Path) -> bool:
    r_script = """
setwd("/home/project/tests/comparative/scenario_temp")
library(ohicore)
library(plyr)
library(dplyr)
conf <- ohicore::Conf("conf")
layers <- ohicore::Layers("layers.csv", "layers")
layers$data$scenario_year <- 2024
scores <- ohicore::CalculateAll(conf, layers)
write.csv(
    scores,
    "/home/project/tests/comparative/scenario_temp/scores.csv",
    na = "NA",
    row.names = FALSE
)
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


def generate_fixture(
    variation: str, overwrite: bool = False, force_regenerate: bool = False
) -> str:
    fixture_path = FIXTURES_DIR / f"{variation}.csv"

    if (
        fixture_path.exists()
        and not overwrite
        and not force_regenerate
        and fixture_path.stat().st_size > 0
    ):
        return "skipped"

    try:
        with acquire_lock():
            if force_regenerate and fixture_path.exists():
                fixture_path.unlink()
            fixture_path.parent.mkdir(parents=True, exist_ok=True)
            prepare_scenario(variation)
            success = run_r_calculation(fixture_path)
            if success:
                return "generated"
            return "failed"
    except RuntimeError as e:
        print(f"    Lock contention: {e}")
        return "failed"
    except Exception as e:
        print(f"    Error: {e}")
        return "failed"


def generate_all_fixtures(
    variations: list[str] | None = None,
    overwrite: bool = False,
    force_regenerate: bool = False,
) -> tuple[int, int, int]:
    if variations is None:
        variations = list(VARIATIONS.keys())

    generated, skipped, failed = 0, 0, 0
    total = len(variations)

    for idx, var in enumerate(variations, 1):
        status = generate_fixture(var, overwrite, force_regenerate)
        if status == "generated":
            print(f"  [{idx}/{total}] {var} generated")
            generated += 1
        elif status == "skipped":
            print(f"  [{idx}/{total}] {var} exists (skipped)")
            skipped += 1
        else:
            print(f"  [{idx}/{total}] {var} failed")
            failed += 1

    print(f"\nSummary: {generated} generated, {skipped} skipped, {failed} failed")
    return generated, skipped, failed


def check_fixtures() -> int:
    missing = []
    for var in VARIATIONS:
        if not (FIXTURES_DIR / f"{var}.csv").exists():
            missing.append(var)
    if missing:
        print(f"Missing {len(missing)} fixtures:")
        for m in missing:
            print(f"  - {m}")
        return 1
    print(f"\u2713 All {len(VARIATIONS)} fixtures exist")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate R dimension-removal fixtures")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--force-regenerate", action="store_true")
    parser.add_argument(
        "--variations",
        nargs="+",
        choices=list(VARIATIONS.keys()),
        default=list(VARIATIONS.keys()),
    )
    args = parser.parse_args()

    if args.check:
        return check_fixtures()

    total = len(args.variations)
    print(f"Generating {total} dimension-removal fixtures...")
    gen, skip, fail = generate_all_fixtures(args.variations, args.overwrite, args.force_regenerate)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
