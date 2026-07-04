"""Tests for the layers.csv-driven declarative column-rename mechanism.

load_layers() renames each layer's declared R source columns (fld_category,
fld_val_num) to the canonical target names the goal functions expect
(fld_category_out, fld_val_out). See ohipy.layers._apply_declared_renames.
"""

import polars as pl

from ohipy.layers import _apply_declared_renames


def _df():
    return pl.DataFrame(
        {"rgn_id": [1, 2], "vernacular_name": ["a", "b"], "catch": [1.0, 2.0]}
    )


def test_renames_category_and_value():
    row = {
        "fld_category": "vernacular_name",
        "fld_category_out": "Spp",
        "fld_val_num": "catch",
        "fld_val_out": "landings",
    }
    out = _apply_declared_renames(_df(), row)
    assert out.columns == ["rgn_id", "Spp", "landings"]


def test_empty_target_leaves_source_untouched():
    # fld_category declared but no *_out target => no rename
    row = {
        "fld_category": "vernacular_name",
        "fld_category_out": "",
        "fld_val_num": "catch",
        "fld_val_out": "",
    }
    out = _apply_declared_renames(_df(), row)
    assert out.columns == ["rgn_id", "vernacular_name", "catch"]


def test_only_value_renamed():
    row = {
        "fld_category": "",
        "fld_category_out": "",
        "fld_val_num": "catch",
        "fld_val_out": "m2",
    }
    out = _apply_declared_renames(_df(), row)
    assert out.columns == ["rgn_id", "vernacular_name", "m2"]


def test_missing_target_columns_is_noop():
    # Backward compat: layers.csv row without the *_out columns at all.
    row = {"fld_category": "vernacular_name", "fld_val_num": "catch"}
    out = _apply_declared_renames(_df(), row)
    assert out.columns == ["rgn_id", "vernacular_name", "catch"]


def test_source_absent_from_df_is_skipped():
    # Declared source column not present in the loaded frame => skip silently.
    row = {"fld_category": "not_a_column", "fld_category_out": "X"}
    out = _apply_declared_renames(_df(), row)
    assert out.columns == ["rgn_id", "vernacular_name", "catch"]


def test_target_collision_is_skipped():
    # Never clobber an existing column: if the target name already exists, skip.
    row = {"fld_val_num": "catch", "fld_val_out": "rgn_id"}
    out = _apply_declared_renames(_df(), row)
    assert out.columns == ["rgn_id", "vernacular_name", "catch"]


def test_source_equals_target_is_noop():
    row = {"fld_val_num": "catch", "fld_val_out": "catch"}
    out = _apply_declared_renames(_df(), row)
    assert out.columns == ["rgn_id", "vernacular_name", "catch"]


def test_load_layers_applies_declared_renames(layers):
    """End-to-end: layers loaded via the real layers.csv have canonical names."""
    data = layers["data"]
    expectations = {
        "fis_meancatch": "Spp",
        "fis_b_bmsy": "Spp",
        "mar_harvest_tonnes": "species",
        "mar_sustainability_scores": "sust_coeff",
        "ico_status": "Specie",
        "cs_habitat_extension": "m2",
        "cp_habitat_extension": "km2",
        "hab_extension": "value",
        "lsp_area_offshore3mn": "cmpa",
        "lsp_area_inland1mn": "cp",
        "le_gdp": "gdp_usd",
    }
    for layer, canonical in expectations.items():
        if layer in data:
            assert canonical in data[layer].columns, (
                f"{layer} missing canonical column {canonical}: {data[layer].columns}"
            )
