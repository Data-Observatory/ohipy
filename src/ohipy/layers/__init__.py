"""OHI Layers Module - Load and manage data layers."""

from pathlib import Path
import pandas as pd


def load_layers(config):
    """
    Load all OHI data layers from CSV files.

    Args:
        config: Configuration dictionary from load_config()

    Returns:
        dict: Layers dictionary with keys:
            - data: dict mapping layer_name -> DataFrame
            - meta: DataFrame with layer metadata from layers.csv
    """
    # Get paths from config
    project_root = Path(__file__).parent.parent.parent.parent
    layers_csv_path = project_root / config['config']['paths']['layers_csv']
    layers_dir = project_root / config['config']['paths']['layers_dir']
    scenario_year = config['config']['scenario_year']

    # Load layers metadata
    layers_meta = pd.read_csv(layers_csv_path)

    # Initialize data dictionary
    layers_data = {}

    # Load each layer file
    for _, row in layers_meta.iterrows():
        layer_name = row['layer']
        filename = row['filename']

        # Skip if filename is missing or NaN
        if pd.isna(filename):
            continue

        # Build full path to layer CSV
        layer_path = layers_dir / filename

        # Load layer data if file exists
        if layer_path.exists():
            try:
                layer_df = pd.read_csv(layer_path)
                layers_data[layer_name] = layer_df
            except Exception as e:
                print(f"Warning: Failed to load layer {layer_name} from {filename}: {e}")
        else:
            print(f"Warning: Layer file not found: {layer_path}")

    # Add scenario_year to data dict for easy access
    layers_data['scenario_year'] = scenario_year

    return {
        'data': layers_data,
        'meta': layers_meta
    }


def select_layers_data(layers, layer_names=None, targets=None, narrow=False):
    """
    Select and merge data from specified layers.

    Args:
        layers: Layers dict from load_layers()
        layer_names: List of layer names to select (optional)
        targets: List of goal codes to select layers for (optional)
        narrow: If True, keep only essential columns (rgn_id, year, value)

    Returns:
        pd.DataFrame: Merged layer data
    """
    layers_data = layers['data']
    layers_meta = layers['meta']

    # Determine which layers to select
    if targets is not None:
        # Filter layers by target goals
        selected_meta = layers_meta[layers_meta['targets'].isin(targets)]
        layer_names = selected_meta['layer'].tolist()
    elif layer_names is None:
        # If no filter specified, use all layers
        layer_names = list(layers_data.keys())

    # Remove 'scenario_year' from layer names (it's metadata, not a layer)
    layer_names = [ln for ln in layer_names if ln != 'scenario_year']

    # Select and optionally merge layers
    if len(layer_names) == 0:
        return pd.DataFrame()

    if len(layer_names) == 1:
        # Single layer - return as is (or narrow)
        df = layers_data.get(layer_names[0], pd.DataFrame())
        if narrow and not df.empty:
            # Keep only essential columns if they exist
            essential_cols = [c for c in ['rgn_id', 'year', 'value'] if c in df.columns]
            if essential_cols:
                df = df[essential_cols]
        return df

    # Multiple layers - merge them
    result = None
    for layer_name in layer_names:
        if layer_name not in layers_data:
            continue

        df = layers_data[layer_name].copy()

        # Standardize column name to include layer name
        # (This prevents column conflicts when merging)
        value_col = None
        for col in df.columns:
            if col not in ['rgn_id', 'year']:
                # Rename value column to layer_layername
                if value_col is None:  # Take first non-id column as value
                    value_col = col
                    df = df.rename(columns={col: f'{layer_name}_{col}'})

        if result is None:
            result = df
        else:
            # Merge on common columns (usually rgn_id, possibly year)
            merge_cols = [c for c in ['rgn_id', 'year'] if c in result.columns and c in df.columns]
            if merge_cols:
                result = result.merge(df, on=merge_cols, how='outer')

    if narrow and result is not None and not result.empty:
        # In narrow mode, keep only rgn_id, year, and first value column
        essential_cols = [c for c in ['rgn_id', 'year'] if c in result.columns]
        value_cols = [c for c in result.columns if c not in essential_cols]
        if value_cols:
            essential_cols.append(value_cols[0])
        result = result[essential_cols]

    return result if result is not None else pd.DataFrame()


# Module exports
__all__ = ['load_layers', 'select_layers_data']
