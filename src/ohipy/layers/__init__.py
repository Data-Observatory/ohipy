"""OHI Layers Module - Load and manage data layers (Polars-native)."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from ohipy.types import ConfigData, LayerDict


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
__all__ = ["load_layers", "select_layers_data"]
