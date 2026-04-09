"""Layer integrity gate tests - validate all 98 declared layers in data/layers.csv."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from ohipy.config import load_config
from ohipy.layers import load_layers
from ohipy.types import LayerDict

# =============================================================================
# CONSTANTS
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CONF_DIR = DATA_DIR / "conf"
LAYERS_DIR = DATA_DIR / "layers"
PARQUET_DIR = LAYERS_DIR / "parquet"
CSV_DIR = LAYERS_DIR / "csv"

# ID columns to exclude when checking if a layer has data
ID_COLUMNS = {"rgn_id", "region_id", "year", "layer"}


# =============================================================================
# FIXTURE: Load layers.csv metadata
# =============================================================================


@pytest.fixture(scope="module")
def layers_meta() -> pl.DataFrame:
    """Load layers.csv metadata as polars DataFrame."""
    layers_csv_path = DATA_DIR / "layers.csv"
    return pl.read_csv(layers_csv_path, null_values=["NA"])


@pytest.fixture(scope="module")
def declared_layers(layers_meta: pl.DataFrame) -> list[str]:
    """Get list of layer names where filename is not null."""
    return layers_meta.filter(pl.col("filename").is_not_null()).get_column("layer").to_list()


@pytest.fixture(scope="module")
def layers_with_filenames(
    layers_meta: pl.DataFrame,
) -> list[tuple[str, str]]:
    """Get list of (layer, filename) tuples where filename is not null."""
    return list(
        layers_meta.filter(pl.col("filename").is_not_null())
        .select(["layer", "filename"])
        .iter_rows()
    )


@pytest.fixture(scope="module")
def loaded_layers() -> LayerDict:
    """Load config and layers once for all tests."""
    config = load_config()
    return load_layers(config)


# =============================================================================
# TEST 1: All declared layers exist on disk
# =============================================================================


@pytest.mark.integrity
def test_all_declared_layers_exist(layers_with_filenames: list[tuple[str, str]]) -> None:
    """Check that every declared layer has a file in parquet/ or csv/ directories."""
    missing: list[str] = []

    for layer, filename in layers_with_filenames:
        # Check parquet path (stem.parquet for .csv filename)
        parquet_path = PARQUET_DIR / (Path(filename).stem + ".parquet")
        csv_path = CSV_DIR / filename

        if not parquet_path.exists() and not csv_path.exists():
            missing.append(f"{layer}: {filename}")

    if missing:
        pytest.fail(
            f"Missing layer files ({len(missing)}):\n" + "\n".join(f"  - {m}" for m in missing)
        )


# =============================================================================
# TEST 2: All declared layers are loadable
# =============================================================================


@pytest.mark.integrity
def test_all_declared_layers_loadable(
    declared_layers: list[str],
    loaded_layers: LayerDict,
) -> None:
    """Check that load_layers() successfully loaded every declared layer."""
    loaded_layer_names = list(loaded_layers["data"].keys())
    # Exclude scenario_year (it's metadata, not a regular layer)
    loaded_layer_names = [n for n in loaded_layer_names if n != "scenario_year"]

    missing: list[str] = []
    for layer in declared_layers:
        if layer not in loaded_layer_names:
            missing.append(layer)

    if missing:
        pytest.fail(
            f"Declared layers not in loaded data ({len(missing)}):\n"
            + "\n".join(f"  - {m}" for m in missing)
        )


# =============================================================================
# TEST 3: All loaded layers are non-empty (have rows)
# =============================================================================


@pytest.mark.integrity
def test_all_loaded_layers_nonempty(
    declared_layers: list[str],
    loaded_layers: LayerDict,
) -> None:
    """Check that every loaded layer has at least one row of data."""
    empty: list[str] = []

    for layer in declared_layers:
        df = loaded_layers["data"].get(layer)
        if df is not None and len(df) == 0:
            empty.append(layer)

    if empty:
        pytest.fail(
            f"Layers with zero rows ({len(empty)}):\n" + "\n".join(f"  - {e}" for e in empty)
        )


# =============================================================================
# TEST 4: All loaded layers have actual data (not all nulls)
# =============================================================================


@pytest.mark.integrity
def test_all_loaded_layers_have_data(
    declared_layers: list[str],
    loaded_layers: LayerDict,
) -> None:
    """Check that every loaded layer has at least some non-null values in value columns."""
    all_null: list[str] = []

    for layer in declared_layers:
        df = loaded_layers["data"].get(layer)
        if df is None:
            continue

        # Identify value columns (all columns except ID columns)
        value_cols = [c for c in df.columns if c not in ID_COLUMNS]

        if not value_cols:
            # No value columns to check, skip this layer
            continue

        # Check if at least one value column has at least one non-null value
        has_data = False
        for col in value_cols:
            null_count = df.select(pl.col(col).null_count())[col][0]
            if null_count < len(df):
                has_data = True
                break

        if not has_data:
            all_null.append(layer)

    if all_null:
        pytest.fail(
            f"Layers with all-null values ({len(all_null)}):\n"
            + "\n".join(f"  - {n}" for n in all_null)
        )


# =============================================================================
# TEST 5: No duplicate layer keys
# =============================================================================


@pytest.mark.integrity
def test_no_duplicate_layer_keys(layers_meta: pl.DataFrame) -> None:
    """Check that layer names are unique in layers.csv."""
    layer_counts = (
        layers_meta.group_by("layer").agg(pl.len().alias("count")).filter(pl.col("count") > 1)
    )

    duplicates = layer_counts.iter_rows()
    dup_list = list(duplicates)

    if dup_list:
        msg = f"Duplicate layer names found ({len(dup_list)}):\n"
        for layer, count in dup_list:
            msg += f"  - {layer}: appears {count} times\n"
        pytest.fail(msg)
