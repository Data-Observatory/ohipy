"""Bridge between chl-schema layers (R's native input) and ohipy-native layers.

R (ohi-core, via the chl submodule) and ohipy read the SAME underlying data in different
column schemas. chl-schema layers (raw R column names, e.g. ``Spp``, ``value_1``) are the
single source of truth — committed wherever a scenario needs them, and fed to R directly
(matches chl's own registry, so R "just works", no rename needed on R's side). ohipy-native
layers (e.g. ``vernacular_name``, ``lsp_porc``) are always DERIVED from chl-schema on the fly
via ``build_ohipy_native()`` — never committed themselves, so there is exactly one column-name
mapping to maintain instead of duplicated committed copies drifting apart.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import polars as pl

REPO = Path(__file__).resolve().parents[2]
CHL = REPO / "chl" / "comunas"
CHL_REGISTRY = CHL / "layers.csv"  # chl-schema registry (fld_value = Spp, value_1, ...)
CHL_LAYERS_DIR = CHL / "layers"  # superset dir; registry selects the real (98) file set
OHIPY_REGISTRY = REPO / "data" / "layers.csv"

# chl-schema column -> ohipy-native column, per layer file. Derived by diffing chl/comunas/
# layers vs data/layers/csv headers. These 9 files need a column rename; every other layer is
# copied verbatim — identical, or (like ao_scores) differing only in column ORDER, which is
# immaterial because load_layers reads by column name, not position.
CHL_TO_OHIPY: dict[str, dict[str, str]] = {
    "fis_meancatch_chl2024.csv": {"Spp": "vernacular_name"},
    "fis_b_bmsy_chl2024.csv": {"Especie": "vernacular_name"},
    "mar_harvest_tonnes_chl2024.csv": {"especie": "species_type"},
    "mar_sustainability_scores_chl2024.csv": {"especie": "species_type", "coeff": "coef"},
    "ico_status_chl2024.csv": {"specie": "scientific_name"},
    "ico_trend_chl2024.csv": {"specie": "scientific_name"},
    "lsp_area_inland1mn_chl2024.csv": {"value_1": "lsp_porc"},
    "lsp_area_offshore3mn_chl2024.csv": {"value_3": "lsp_porc"},
    "hab_extension_chl2024.csv": {"value": "area_km2"},
}


def registry_filenames(registry_csv: Path) -> set[str]:
    """Return the set of layer filenames a layers.csv registry declares."""
    return set(pl.read_csv(registry_csv, infer_schema_length=200)["filename"].drop_nulls().to_list())


def assert_registries_aligned() -> None:
    """Guard: chl's registry and ohipy's registry must declare the SAME layer filenames.

    A drift here means a layer exists for one engine but not the other, silently scoring on
    a partial layer set instead of crashing — this check turns that into a loud failure.
    """
    chl_files = registry_filenames(CHL_REGISTRY)
    ohipy_files = registry_filenames(OHIPY_REGISTRY)
    if chl_files != ohipy_files:
        only_chl = sorted(chl_files - ohipy_files)
        only_ohipy = sorted(ohipy_files - chl_files)
        raise RuntimeError(
            "registry filename mismatch between chl/comunas/layers.csv and data/layers.csv "
            f"(only in chl: {only_chl}; only in ohipy: {only_ohipy})"
        )


def materialize_chl_subset(out_dir: Path) -> None:
    """Copy exactly the registered chl-schema layer files into out_dir.

    chl/comunas/layers/ is a superset (older-year variants, stray .xlsx, etc.) — this copies
    only the filenames chl's OWN registry declares, so noise injection and R's "original"
    baseline input are never accidentally polluted by unregistered files.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(registry_filenames(CHL_REGISTRY)):
        shutil.copyfile(CHL_LAYERS_DIR / name, out_dir / name)


def build_ohipy_native(src_dir: Path, out_dir: Path) -> None:
    """Derive ohipy-native layers from chl-schema layers in src_dir into out_dir.

    Pure copy + rename of the 9 CHL_TO_OHIPY files — same underlying data as src_dir (which
    drives R), only the differing column names change, so R and ohipy score the same data in
    their own schemas. Never re-injects noise or re-reads from data/; out_dir is meant to be a
    throwaway temp dir, not committed.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(src_dir.glob("*.csv")):
        dst = out_dir / src.name
        renames = CHL_TO_OHIPY.get(src.name)
        if renames:
            df = pl.read_csv(src, infer_schema_length=100000)
            clash = set(renames.values()) & set(df.columns)
            assert not clash, f"{src.name}: rename target(s) already present: {clash}"
            df.rename(renames).write_csv(dst)
        else:
            shutil.copyfile(src, dst)
