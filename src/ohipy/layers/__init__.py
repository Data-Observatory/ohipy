"""OHI Layers Module - Load and manage data layers (Polars-native)."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from ohipy.types import ConfigData, LayerDict

# Layer names (as keyed in the loaded data dict / the `layer` column of layers.csv)
# whose goal functions perform their OWN multi-year (rolling-window) filtering
# internally. For these layers the R pipeline stamps ohi_year as a plain copy of
# `year` (one value per row via add_ohi_year()), so filtering
# `ohi_year == scenario_year` here would collapse the layer to a single year and
# silently break the downstream multi-year trend / rolling-window computation
# (e.g. a 5-year trend computed from a single data point).
#
# These layers must therefore be loaded with ALL years intact; their goal
# functions (FIS/MAR/NP/TR/CS/CP/HAB/LSP/ECO/LIV in ohipy/src/ohipy/goals/*.py)
# select the years they need via range(scen_year - 4, scen_year + 1) or a
# year >= max_year - 4 window.
#
# NOTE: this list uses ohipy LAYER NAMES (the dict keys the goal functions call
# data_layers.get() with), NOT the S3 parquet filename stems. It is the
# authoritative, ohipy-side mirror of the `_NO_OHI_YEAR` filename set in the
# main repo's infra/ohipy/container/normalize_layers.py.
ROLLING_WINDOW_LAYERS: frozenset[str] = frozenset({
    # FIS (5-yr window; fis.py filters year.is_in(trend_years))
    "fis_meancatch",
    "fis_b_bmsy",
    # MAR (5-yr window; mar.py filters year.is_in(trend_years))
    "mar_harvest_tonnes",
    "mar_sustainability_scores",  # has no year column; included for safety/parity
    # NP (5-yr window; np.py filters year.is_in(trend_years))
    "np_harvest_tonnes",
    "np_harvest_tonnes_weigth",  # note: 'weigth' typo preserved from layers.csv
    "np_fofm_scores",
    "np_seaweed_sust",
    # NOTE: np_harvest_tonnes_relative is DELIBERATELY excluded. The R prep
    # (prep_NP.R get_np_harvest_relative) window-explodes it: each ohi_year x
    # carries the full [x-4, x] window as distinct rows, so the same `year`
    # appears under multiple ohi_year tags. It MUST be ohi_year-filtered to the
    # scenario window, else np.py's join on `year` (np.py ~L112) would carry
    # cross-window duplicate years and inflate the status. See prep_NP.R L198-221.
    # TR (multi-year trend; tr.py computes trend over trend_years)
    "tr_sustainability",
    "tr_factor",
    # NOTE: tr_jobs_pct_tourism is DELIBERATELY excluded — same window-explosion
    # pattern as np_harvest_tonnes_relative (prep_TR.R get_jobs_pct_tourism
    # L55-70: mutate(ohi_year = x) per [x-4, x] window). Must stay ohi_year-filtered.
    # CS (5-yr window; cs.py trend over trend_years)
    "cs_habitat_extension",
    # CP (5-yr window; cp.py filters year >= scen_year - 4)
    "cp_habitat_extension",
    # HAB (5-yr window; hab.py trend over trend_years)
    "hab_extension",
    # LSP (5-yr window; lsp.py trend over trend_years)
    "lsp_area_offshore3mn",
    "lsp_area_inland1mn",
    # ECO (le_gdp: eco.py filters year >= max_year - 4)
    "le_gdp",
    # LIV (le.py/liv.py filter year >= max_year - 4)
    "le_workforcesize_adj",
    "le_unemployment",
    "le_jobs_sector",
    "le_wage_sector",
})


# Declarative column-rename mechanism driven by layers.csv.
#
# Each layer row in layers.csv can declare the SOURCE column names emitted by
# the R pipeline together with the canonical TARGET names the ohipy goal
# functions expect, so the per-layer column translation lives in ONE auditable
# table instead of being hand-encoded as a `.rename()` inside each goals/*.py:
#
#   * fld_category      -> the layer's category/grouping column as emitted by R
#                          (e.g. vernacular_name / species_type / scientific_name
#                          / habitat / sector), or empty if the layer has none.
#     fld_category_out  -> canonical name load_layers() renames it to (e.g. Spp,
#                          species, Specie). Empty => leave the source untouched.
#
#   * fld_val_num       -> the layer's primary numeric value column as emitted
#                          by R (e.g. catch, tonnes, coef, value, area_km2,
#                          lsp_porc, gdp).
#     fld_val_out       -> canonical name load_layers() renames it to (e.g. m2,
#                          km2, value, cp, cmpa, sust_coeff, gdp_usd). Empty =>
#                          leave the source untouched.
#
# The region-id column (fld_id_num, always "rgn_id" post add_rgn_id on the R
# side) is intentionally NOT renamed here — rgn_id is already the OHI-standard
# name; goals that want a different local id name (e.g. region_id) still do that
# rename themselves.
#
# Each (source, target) pair maps a *_out target column back to its source
# declaration column. Add a pair here to cover another declared field.
_DECLARED_RENAME_FIELDS: tuple[tuple[str, str], ...] = (
    ("fld_category", "fld_category_out"),
    ("fld_val_num", "fld_val_out"),
)


def _apply_declared_renames(df: pl.DataFrame, row: dict) -> pl.DataFrame:
    """Rename a layer's declared source columns to their canonical target names.

    For each (source_field, target_field) in _DECLARED_RENAME_FIELDS, if the
    layers.csv row declares both a non-empty source column name and a non-empty
    target name, and the source column is present in df (and the target is not
    already a column), rename source -> target. This is a no-op when the target
    columns are absent from layers.csv (backward compatible) or empty.
    """
    renames: dict[str, str] = {}
    for src_field, out_field in _DECLARED_RENAME_FIELDS:
        src = row.get(src_field)
        out = row.get(out_field)
        if src is None or out is None:
            continue
        src = str(src).strip()
        out = str(out).strip()
        if not src or not out or src == out:
            continue
        if src in df.columns and out not in df.columns:
            renames[src] = out
    if renames:
        df = df.rename(renames)
    return df


def _filter_by_ohi_year(
    df: pl.DataFrame, scenario_year: int | None, layer_name: str | None = None
) -> pl.DataFrame:
    """Filter layer DataFrame by ohi_year scenario tag.

    When ohi_year column exists and scenario_year is set, keeps only rows
    where ohi_year matches the scenario year or is null (static layers).
    Returns df unchanged when ohi_year column is absent (backward compat).

    Rolling-window layers (see ROLLING_WINDOW_LAYERS) are returned unchanged
    regardless of ohi_year, because their goal functions need all years and the
    R-side ohi_year on them is merely a plain copy of `year`.
    """
    if layer_name is not None and layer_name in ROLLING_WINDOW_LAYERS:
        return df
    if "ohi_year" not in df.columns or scenario_year is None:
        return df
    return df.filter(
        (pl.col("ohi_year") == scenario_year) | (pl.col("ohi_year").is_null())
    )


def load_layers(config: ConfigData) -> LayerDict:
    """
    Load all OHI data layers from Parquet or CSV files.

    Args:
        config: Configuration dictionary from load_config()

    Returns:
        dict: Layers dictionary with keys:
            - data: dict mapping layer_name -> polars DataFrame
            - meta: polars DataFrame with layer metadata from layers.csv
    """
    # Get paths from config
    project_root = Path(__file__).parent.parent.parent.parent
    layers_csv_path = project_root / config["config"]["paths"]["layers_csv"]
    layers_dir = project_root / config["config"]["paths"]["layers_dir"]
    parquet_dir = layers_dir.parent / "parquet"
    scenario_year = config["config"]["scenario_year"]
    layer_format = config["config"].get("layer_format", "parquet")

    # Load layers metadata using Polars (keep as polars)
    layers_meta = pl.read_csv(layers_csv_path, null_values=["NA"])
    # Initialize data dictionary
    layers_data = {}

    # Load each layer file using Polars
    for row in layers_meta.iter_rows(named=True):
        layer_name = row["layer"]
        filename = row["filename"]

        # Skip if filename is missing or null
        if filename is None:
            continue

        # Build full path to layer CSV
        layer_path = layers_dir / filename
        parquet_path = parquet_dir / (Path(filename).stem + ".parquet")
        layer_df = None

        # Load based on user's format preference with fallback
        if layer_format == "csv":
            if layer_path.exists():
                try:
                    layer_df = pl.read_csv(layer_path, null_values=["NA"])
                except Exception as e:
                    print(f"Warning: Failed to load CSV layer {layer_name}: {e}")
            if layer_df is None and parquet_path.exists():
                try:
                    layer_df = pl.read_parquet(parquet_path)
                except Exception as e:
                    print(f"Warning: Failed to load Parquet fallback for {layer_name}: {e}")
        else:
            if parquet_path.exists():
                try:
                    layer_df = pl.read_parquet(parquet_path)
                except Exception as e:
                    print(f"Warning: Failed to load Parquet layer {layer_name}: {e}")
            if layer_df is None and layer_path.exists():
                try:
                    layer_df = pl.read_csv(layer_path, null_values=["NA"])
                except Exception as e:
                    print(f"Warning: Failed to load CSV fallback for {layer_name}: {e}")

        if layer_df is not None:
            # Normalize declared source columns to their canonical target names
            # (layers.csv is the single source of truth for this mapping) before
            # any year filtering or hand-off to goal functions.
            layer_df = _apply_declared_renames(layer_df, row)
            layer_df = _filter_by_ohi_year(layer_df, scenario_year, layer_name)
            if layer_df.is_empty():
                print(
                    f"Warning: Layer {layer_name} has ohi_year but no rows match "
                    f"scenario_year={scenario_year}"
                )
            layers_data[layer_name] = layer_df
        else:
            print(f"Warning: Layer file not found: {layer_path}")

    # Add scenario_year to data dict for easy access
    layers_data["scenario_year"] = scenario_year

    return {"data": layers_data, "meta": layers_meta}


def select_layers_data(
    layers: LayerDict,
    layer_names: list[str] | None = None,
    targets: list[str] | None = None,
    narrow: bool = False,
) -> pl.DataFrame:
    """
    Select and merge data from specified layers.

    Args:
        layers: Layers dict from load_layers()
        layer_names: List of layer names to select (optional)
        targets: List of goal codes to select layers for (optional)
        narrow: If True, keep only essential columns (rgn_id, year, value)

    Returns:
        pl.DataFrame: Merged layer data
    """
    layers_data = layers["data"]
    layers_meta = layers["meta"]

    # Determine which layers to select
    if targets is not None:
        # Filter layers by target goals
        selected_meta = layers_meta.filter(pl.col("targets").is_in(targets))
        layer_names = selected_meta["layer"].to_list()
    elif layer_names is None:
        # If no filter specified, use all layers
        layer_names = list(layers_data.keys())

    # Remove 'scenario_year' from layer names (it's metadata, not a layer)
    layer_names = [ln for ln in layer_names if ln != "scenario_year"]

    # Select and optionally merge layers
    if len(layer_names) == 0:
        return pl.DataFrame()

    if len(layer_names) == 1:
        # Single layer - return as is (or narrow)
        df = layers_data.get(layer_names[0], pl.DataFrame())
        if narrow and not df.is_empty():
            # Keep only essential columns if they exist
            essential_cols = [c for c in ["rgn_id", "year", "value"] if c in df.columns]
            if essential_cols:
                df = df.select(essential_cols)
        return df  # type: ignore[no-any-return]

    # Multiple layers - merge them
    result = None
    for layer_name in layer_names:
        if layer_name not in layers_data:
            continue

        df = layers_data[layer_name].clone()

        # Standardize column name to include layer name
        # (This prevents column conflicts when merging)
        value_col = None
        for col in df.columns:
            if col not in ["rgn_id", "year"]:
                # Rename value column to layer_layername
                if value_col is None:  # Take first non-id column as value
                    value_col = col
                    df = df.rename({col: f"{layer_name}_{col}"})

        if result is None:
            result = df
        else:
            # Merge on common columns (usually rgn_id, possibly year)
            merge_cols = [c for c in ["rgn_id", "year"] if c in result.columns and c in df.columns]
            if merge_cols:
                result = result.join(df, on=merge_cols, how="full")

    if narrow and result is not None and not result.is_empty():
        # In narrow mode, keep only rgn_id, year, and first value column
        essential_cols = [c for c in ["rgn_id", "year"] if c in result.columns]
        value_cols = [c for c in result.columns if c not in essential_cols]
        if value_cols:
            essential_cols.append(value_cols[0])
        result = result.select(essential_cols)

    return result if result is not None else pl.DataFrame()


# Module exports
__all__ = ["ROLLING_WINDOW_LAYERS", "load_layers", "select_layers_data"]
