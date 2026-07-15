"""ideos_2026 comparative scenario: build/regenerate fixtures and run ohipy offline.

Mirrors how the other R-vs-ohipy parity tests work: each engine reads layers in its OWN
native column schema (same underlying data, compared on results):

  * R (ohi-core) reads the chl-schema layers (species column e.g. ``Especie``/``Spp``) via
    chl's own registry ``chl/comunas/layers.csv`` — same as ``tests/comparative/calculate_scores.r``.
  * ohipy reads the ohipy-native layers (raw parquet names e.g. ``vernacular_name``) via the
    LIVE repo ``data/layers.csv`` — same as ``tests/test_parity_full.py`` — which load_layers()
    renames to canonical names (``Spp`` …) through its ``fld_category_out`` column.

Committed artifacts under ``tests/comparative/``:
  scenarios/ideos_2026/layers/csv/*.csv        -- chl-schema layers (drive the R baseline)
  scenarios/ideos_2026/layers_ohipy/csv/*.csv  -- ohipy-native layers (ohipy reads these)
  scenarios/ideos_2026/conf/*.csv              -- 6 conf CSVs used for generation (ohipy matrices)
  fixtures/ideos_2026/baseline.csv             -- R ohi-core reference scores

Using the LIVE ``data/layers.csv`` (not a snapshot) keeps ohipy consistent with ohipy's own
code when its layer schema evolves — a stale registry snapshot is what broke this test after
an ohipy upgrade changed the species-column rename mechanism.

Regeneration (``OHI_AUTO_GENERATE_FIXTURES=1``) reuses the ALREADY-downloaded IDEOS parquet
(the S3 pull is done out-of-band; see ``proj-IDEOS-metas/scripts/sync_from_s3.sh``).
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
from pathlib import Path

import polars as pl
import yaml

# --- locations ------------------------------------------------------------
REPO = Path(__file__).resolve().parents[2]
CHL = REPO / "chl" / "comunas"
SCENARIO = "ideos_2026"
SCEN_DIR = REPO / "tests" / "comparative" / "scenarios" / SCENARIO
LAYERS_DIR = SCEN_DIR / "layers" / "csv"           # chl-schema (for R)
LAYERS_DIR_OHIPY = SCEN_DIR / "layers_ohipy" / "csv"  # ohipy-native (for ohipy)
CONF_DIR = SCEN_DIR / "conf"
OHIPY_REGISTRY = REPO / "data" / "layers.csv"      # LIVE ohipy registry (has fld_category_out)
FIXTURE = REPO / "tests" / "comparative" / "fixtures" / SCENARIO / "baseline.csv"
CALC_R = REPO / "tests" / "comparative" / "calculate_scores_ideos.r"
DOCKER_IMAGE = "ohicore-r-env"

CONF_CSVS = (
    "goals.csv", "pressures_matrix.csv", "resilience_matrix.csv",
    "pressure_categories.csv", "resilience_categories.csv", "scenario_data_years.csv",
)

# chl-schema column -> ohipy-native column, per layer file. Derived by diffing
# chl/comunas/layers vs data/layers/csv headers. These 9 files need a column rename; every
# other layer is copied verbatim — identical, or (like ao_scores) differing only in column
# ORDER, which is immaterial because load_layers reads by column name, not position.
CHL_TO_OHIPY: dict[str, dict[str, str]] = {
    "fis_meancatch_chl2024.csv": {"Spp": "vernacular_name"},
    "fis_b_bmsy_chl2024.csv": {"Especie": "vernacular_name"},
    "mar_harvest_tonnes_chl2024.csv": {"especie": "species_type"},
    "mar_sustainability_scores_chl2024.csv": {"especie": "species_type", "coeff": "coef"},
    "ico_status_chl2024.csv": {"specie": "scientific_name"},
    "ico_trend_chl2024.csv": {"specie": "scientific_name"},
    "lsp_area_inland1mn_chl2024.csv": {"value_1": "area_int_km2"},
    "lsp_area_offshore3mn_chl2024.csv": {"value_3": "area_int_km2"},
    "hab_extension_chl2024.csv": {"value": "area_km2"},
}


def fixture_exists() -> bool:
    """True when the committed offline artifacts are all present."""
    return (
        FIXTURE.exists()
        and CONF_DIR.exists()
        and LAYERS_DIR_OHIPY.exists()
        and any(LAYERS_DIR_OHIPY.glob("*.csv"))
    )


# --- offline ohipy run (default test path) --------------------------------
def run_ohipy_offline() -> pl.DataFrame:
    """Run ohipy on the ohipy-native scenario layers + the conf snapshot; return
    [region_id, goal, dimension, score].

    Loads the shipped config.yaml whole (preserving constants/layers/element_mappings) and
    overrides only the paths to ABSOLUTE locations (load_config/load_layers resolve against
    ohipy's own project_root, so relative paths would point at the wrong tree). The layer
    registry is the LIVE data/layers.csv so the rename stays in lock-step with ohipy's code.
    """
    from ohipy.calculate_all import calculate_all
    from ohipy.config import load_config
    from ohipy.layers import load_layers

    cfg = yaml.safe_load((REPO / "src" / "ohipy" / "config" / "config.yaml").read_text())
    cfg["layer_format"] = "csv"
    cfg["scenario_year"] = 2024
    cfg["paths"].update(
        {
            "goals_csv": str(CONF_DIR / "goals.csv"),
            "pressures_matrix_csv": str(CONF_DIR / "pressures_matrix.csv"),
            "resilience_matrix_csv": str(CONF_DIR / "resilience_matrix.csv"),
            "pressure_categories_csv": str(CONF_DIR / "pressure_categories.csv"),
            "resilience_categories_csv": str(CONF_DIR / "resilience_categories.csv"),
            "scenario_data_years_csv": str(CONF_DIR / "scenario_data_years.csv"),
            "layers_csv": str(OHIPY_REGISTRY),
            "layers_dir": str(LAYERS_DIR_OHIPY),
        }
    )
    for key in (
        "goals_csv", "pressures_matrix_csv", "resilience_matrix_csv",
        "pressure_categories_csv", "resilience_categories_csv",
        "scenario_data_years_csv", "layers_csv", "layers_dir",
    ):
        assert Path(cfg["paths"][key]).is_absolute(), f"path {key} must be absolute"

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
        yaml.safe_dump(cfg, fh)
        tmp_yaml = Path(fh.name)
    try:
        config = load_config(config_path=tmp_yaml, year=2024)
        scores = calculate_all(config, load_layers(config))
    finally:
        tmp_yaml.unlink(missing_ok=True)
    # Drop null/NaN scores (matches test_r_parity/test_parity_full). NOTE the R fixture keeps
    # its rows, so goals ohipy computes as NaN surface as `py_missing` in compare_scores.
    return scores.select(
        pl.col("region_id").cast(pl.Int64),
        pl.col("goal"),
        pl.col("dimension"),
        pl.col("score").cast(pl.Float64),
    ).filter(pl.col("score").is_not_null() & ~pl.col("score").is_nan())


def load_r_fixture() -> pl.DataFrame:
    """Read the committed R reference scores as [region_id, goal, dimension, score]."""
    df = pl.read_csv(FIXTURE)
    df.columns = [c.strip() for c in df.columns]
    return df.select(
        pl.col("region_id").cast(pl.Int64),
        pl.col("goal"),
        pl.col("dimension"),
        pl.col("score").cast(pl.Float64),
    )


# --- regeneration (gated: OHI_AUTO_GENERATE_FIXTURES=1) --------------------
def _convert_chl_schema(parquet_dir: Path) -> None:
    """parquet -> chl-schema layer CSVs (reuses scripts/convert_ideos_layers.py)."""
    spec = importlib.util.spec_from_file_location(
        "convert_ideos_layers", REPO / "scripts" / "convert_ideos_layers.py"
    )
    assert spec and spec.loader
    conv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conv)
    conv.PARQUET_DIR = parquet_dir  # already-downloaded IDEOS parquet (S3 pull done out-of-band)
    conv.OUT_DIR = LAYERS_DIR
    conv.main()


def build_ohipy_native() -> None:
    """Derive ohipy-native layers from the chl-schema layers: copy every file, and for the
    9 files whose species/value column name differs, rename to the ohipy-native name.

    Same underlying data as the chl-schema layers (which drive the R baseline) — only the
    differing column names change — so R and ohipy score the same data in their own schemas.
    """
    LAYERS_DIR_OHIPY.mkdir(parents=True, exist_ok=True)
    for src in sorted(LAYERS_DIR.glob("*.csv")):
        dst = LAYERS_DIR_OHIPY / src.name
        renames = CHL_TO_OHIPY.get(src.name)
        if renames:
            pl.read_csv(src).rename(renames).write_csv(dst)
        else:
            shutil.copyfile(src, dst)


def _snapshot_conf() -> None:
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    for f in CONF_CSVS:
        shutil.copyfile(CHL / "conf" / f, CONF_DIR / f)


def _generate_r_fixture() -> None:
    """Run ohi-core in Docker on the chl-schema scenario layers -> baseline.csv."""
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "docker", "run", "--rm",
            "-v", f"{REPO}:/home/project",
            "-w", "/home/project/chl/comunas",
            DOCKER_IMAGE,
            "Rscript", "/home/project/tests/comparative/calculate_scores_ideos.r",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def regenerate(parquet_dir: Path | str) -> None:
    """Full regen from already-downloaded parquet. Strictly ordered so the offline compare
    never sees stale conf/layers:
        convert (chl-schema) -> derive ohipy-native -> snapshot conf -> R fixture.
    """
    # The R registry (chl/comunas/layers.csv) drives conversion + scoring; the ohipy-native
    # derivation renames to columns the LIVE data/layers.csv expects. The two registries are
    # NOT byte-identical (data/layers.csv carries the extra fld_category_out/fld_val_out
    # columns ohipy uses to rename) — guard only that they list the SAME layer filenames.
    chl_files = set(pl.read_csv(CHL / "layers.csv")["filename"].drop_nulls().to_list())
    ohipy_files = set(pl.read_csv(OHIPY_REGISTRY)["filename"].drop_nulls().to_list())
    if chl_files != ohipy_files:
        only_chl = sorted(chl_files - ohipy_files)
        only_ohipy = sorted(ohipy_files - chl_files)
        raise RuntimeError(
            "registry filename mismatch between chl/comunas/layers.csv and data/layers.csv "
            f"(only in chl: {only_chl}; only in ohipy: {only_ohipy}) — "
            "re-check the ideos_2026 scenario before regenerating"
        )
    _convert_chl_schema(Path(parquet_dir))
    build_ohipy_native()
    _snapshot_conf()
    _generate_r_fixture()
