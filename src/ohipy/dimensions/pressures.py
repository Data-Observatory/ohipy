# pyright: reportAny=false, reportExplicitAny=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnusedVariable=false
"""Pressure dimension calculator for OHI."""

from typing import Any

import polars as pl
import polars.selectors as cs


def _ensure_polars(df: Any) -> pl.DataFrame | None:
    """Convert incoming tabular object to polars if needed."""
    if df is None:
        return None
    if isinstance(df, pl.DataFrame):
        return df.clone()
    if hasattr(df, "to_pandas"):
        return pl.from_pandas(df.to_pandas())
    return pl.DataFrame(df)


def _first_id_column(columns: list[str]) -> str | None:
    matches = [c for c in columns if "id" in c.lower() or c == "rgn_id"]
    return matches[0] if matches else None


def _first_numeric_column(df: pl.DataFrame, excluded: set[str]) -> str | None:
    numeric_cols = df.select(cs.numeric()).columns
    for c in numeric_cols:
        if c in excluded:
            continue
        return c
    return None


def calculate_pressures_all(config: dict[str, Any], layers: dict[str, Any]) -> pl.DataFrame:
    """
    Calculate pressure scores for all goals across all regions.

    Translates ohicore/R/CalculatePressuresAll.R

    Args:
        config: Configuration dictionary from load_config()
        layers: Layers dictionary from load_layers()

    Returns:
        DataFrame with columns: goal, dimension, region_id, score
    """

    # Load pressure matrix
    p_matrix = _ensure_polars(config["pressures_matrix"])
    if p_matrix is None:
        raise ValueError("Missing pressures_matrix")

    # Reshape matrix from wide to long format
    id_cols = ["goal", "element", "element_name"]
    layer_cols = [c for c in p_matrix.columns if c not in id_cols]

    p_matrix = p_matrix.unpivot(
        index=id_cols,
        on=layer_cols,
        variable_name="layer",
        value_name="m_intensity",
    )

    # Filter out NA intensities and drop element_name
    p_matrix = p_matrix.filter(pl.col("m_intensity").is_not_null()).select(
        ["goal", "element", "layer", "m_intensity"]
    )
    # Fill NA element with empty string to avoid groupby dropna=True excluding them
    p_matrix = p_matrix.with_columns(pl.col("element").fill_null(""))

    # Load pressure categories
    p_categories = _ensure_polars(config["pressure_categories"])
    if p_categories is None:
        raise ValueError("Missing pressure_categories")

    # PATCH: Fix duplicate pres_n_explora in categories which should likely be pres_n_proyexplora
    dupes = (
        p_categories.with_row_index("_idx")
        .filter(pl.col("layer") == "pres_n_explora")
        .select("_idx")
        .to_series()
        .to_list()
    )
    if len(dupes) >= 2:
        second_idx = int(dupes[1])
        p_categories = (
            p_categories.with_row_index("_idx")
            .with_columns(
                pl.when(pl.col("_idx") == second_idx)
                .then(pl.lit("pres_n_proyexplora"))
                .otherwise(pl.col("layer"))
                .alias("layer")
            )
            .drop("_idx")
        )

    # Get pressure element mappings
    p_element = config["config"].get("element_mappings", {}).get("pressures", {})
    if p_element:
        p_element_df = pl.DataFrame(
            {
                "goal": list(p_element.keys()),
                "layer": list(p_element.values()),
            }
        )
    else:
        p_element_df = None

    # Get gamma weighting
    p_gamma = float(config["config"]["constants"]["pressures_gamma"])

    # Get list of pressure layers
    p_layers = sorted(layer_cols)

    # Get regions - load region labels layer
    region_layer_name = config["config"]["layers"]["region_labels"]
    region_layer = _ensure_polars(layers["data"].get(region_layer_name))
    if region_layer is None:
        raise ValueError(f"Missing region layer: {region_layer_name}")

    # Extract region IDs (first numeric column is typically the ID)
    id_col = _first_id_column(region_layer.columns)
    if id_col is None:
        raise ValueError("Could not find region ID column")

    regions_df = region_layer.select(pl.col(id_col).alias("region_id"))
    regions_vector = regions_df.get_column("region_id").to_list()

    # Create ecological/social weighting
    eco_soc_weight = pl.DataFrame(
        {
            "category": ["ecological", "social"],
            "weight": [p_gamma, 1 - p_gamma],
        }
    )

    # Handle scenario data years
    if "scenario_data_years" in config and len(config["scenario_data_years"]) > 0:
        scenario_data_year = _ensure_polars(config["scenario_data_years"])
        if scenario_data_year is None:
            scenario_data_year = pl.DataFrame({"layer": p_layers, "year": [20100] * len(p_layers)})
        else:
            scenario_data_year = (
                scenario_data_year.filter(pl.col("layer_name").is_in(p_layers))
                .filter(pl.col("scenario_year") == layers["data"]["scenario_year"])
                .select(
                    [
                        pl.col("layer_name").alias("layer"),
                        pl.col("data_year").alias("year"),
                    ]
                )
            )

            layers_no_years = set(p_layers) - set(scenario_data_year.get_column("layer").to_list())
            if layers_no_years:
                no_years_df = pl.DataFrame(
                    {
                        "layer": list(layers_no_years),
                        "year": [20100] * len(layers_no_years),
                    }
                )
                scenario_data_year = pl.concat([scenario_data_year, no_years_df], how="vertical")
    else:
        scenario_data_year = pl.DataFrame({"layer": p_layers, "year": [20100] * len(p_layers)})

    scenario_data_year = scenario_data_year.with_columns(
        pl.col("year").cast(pl.Int64, strict=False).fill_null(20100)
    )

    # Load pressure layer data - collect all layers
    p_rgn_layers_list: list[pl.DataFrame] = []
    for layer_name in p_layers:
        layer_data = layers["data"].get(layer_name)
        if layer_data is None:
            continue

        df = _ensure_polars(layer_data)
        if df is None:
            continue

        # Find ID column
        local_id_col = _first_id_column(df.columns)
        if local_id_col is None:
            continue

        # Find value column (typically 'val_num' or 'value')
        val_candidates = [c for c in df.columns if c in ["val_num", "value"]]
        if val_candidates:
            val_col = val_candidates[0]
        else:
            fallback = [c for c in df.columns if c not in [local_id_col, "year"]]
            if not fallback:
                continue
            val_col = fallback[0]

        # Prepare data
        cols_to_keep = [local_id_col, val_col]
        if "year" in df.columns:
            cols_to_keep.append("year")
            df = df.select(cols_to_keep)
        else:
            df = df.select(cols_to_keep).with_columns(pl.lit(None).alias("year"))

        df = (
            df.rename({local_id_col: "region_id", val_col: "val_num"})
            .with_columns(pl.lit(layer_name).alias("layer"))
            .select(["region_id", "val_num", "year", "layer"])
        )

        p_rgn_layers_list.append(df)

    if not p_rgn_layers_list:
        raise ValueError("No pressure layer data found")

    p_rgn_layers_data = pl.concat(p_rgn_layers_list, how="vertical_relaxed")

    # Filter and prepare data
    p_rgn_layers_data = (
        p_rgn_layers_data.filter(pl.col("region_id").is_in(regions_vector))
        .filter(pl.col("val_num").is_not_null())
        .with_columns(pl.col("year").cast(pl.Int64, strict=False).fill_null(20100))
    )

    # Join with scenario years
    p_rgn_layers = scenario_data_year.join(p_rgn_layers_data, on=["year", "layer"], how="inner")
    p_rgn_layers = p_rgn_layers.select(["region_id", "val_num", "layer"])

    # Merge matrix with categories
    p_matrix = (
        p_matrix.with_columns(pl.col("m_intensity").cast(pl.Float64, strict=False))
        .join(p_categories, on="layer", how="inner")
        .with_columns(
            pl.col("m_intensity")
            .max()
            .over(["goal", "element", "category", "subcategory"])
            .alias("max_subcategory")
        )
    )

    # Merge with region data
    rgn_matrix = p_matrix.join(p_rgn_layers, on="layer", how="inner")

    # Calculate pressure intensity
    rgn_matrix = rgn_matrix.with_columns(
        (pl.col("m_intensity") * pl.col("val_num").cast(pl.Float64, strict=False)).alias(
            "pressure_intensity"
        )
    )

    # Separate ecological and social pressures
    # Ecological: sum / 3, capped at 1
    calc_pressure_eco = (
        rgn_matrix.filter(pl.col("category") == "ecological")
        .group_by(["goal", "element", "category", "subcategory", "max_subcategory", "region_id"])
        .agg(pl.col("pressure_intensity").sum().alias("pressure_intensity"))
        .with_columns((pl.col("pressure_intensity") / 3).clip(upper_bound=1).alias("cum_pressure"))
        .drop("pressure_intensity")
    )

    # Social: mean, capped at 1
    calc_pressure_soc = (
        rgn_matrix.filter(pl.col("category") == "social")
        .group_by(["goal", "element", "category", "subcategory", "max_subcategory", "region_id"])
        .agg(pl.col("pressure_intensity").mean().alias("pressure_intensity"))
        .with_columns(pl.col("pressure_intensity").clip(upper_bound=1).alias("cum_pressure"))
        .drop("pressure_intensity")
    )

    # Combine ecological and social
    calc_pressure = pl.concat([calc_pressure_eco, calc_pressure_soc], how="vertical_relaxed")

    # Weighted mean of subcategories
    calc_pressure = (
        calc_pressure.with_columns(
            [
                pl.col("max_subcategory").cast(pl.Float64).alias("max_subcategory"),
                pl.col("cum_pressure").cast(pl.Float64).alias("cum_pressure"),
            ]
        )
        .with_columns((pl.col("cum_pressure") * pl.col("max_subcategory")).alias("_weighted"))
        .group_by(["goal", "element", "category", "region_id"])
        .agg(
            [
                pl.col("_weighted").sum().alias("_weighted_sum"),
                pl.col("max_subcategory").sum().alias("_weight_sum"),
            ]
        )
        .with_columns(
            pl.when(pl.col("_weight_sum") == 0)
            .then(None)
            .otherwise(pl.col("_weighted_sum") / pl.col("_weight_sum"))
            .alias("pressure")
        )
        .select(["goal", "element", "category", "region_id", "pressure"])
    )

    # Combine ecological and social using gamma weighting
    calc_pressure = (
        calc_pressure.join(eco_soc_weight, on="category", how="inner")
        .with_columns(
            [
                pl.col("weight").cast(pl.Float64).alias("weight"),
                pl.col("pressure").cast(pl.Float64).alias("pressure"),
            ]
        )
        .with_columns((pl.col("pressure") * pl.col("weight")).alias("_weighted"))
        .group_by(["goal", "element", "region_id"])
        .agg(
            [
                pl.col("_weighted").sum().alias("_weighted_sum"),
                pl.col("weight").sum().alias("_weight_sum"),
            ]
        )
        .with_columns(
            pl.when(pl.col("_weight_sum") == 0)
            .then(None)
            .otherwise(pl.col("_weighted_sum") / pl.col("_weight_sum"))
            .alias("pressure")
        )
        .select(["goal", "element", "region_id", "pressure"])
    )

    # Handle goals with elements
    if p_element_df is not None and p_element_df.height > 0:
        p_element_layers_list: list[pl.DataFrame] = []

        for layer_name in p_element_df.get_column("layer").unique().to_list():
            layer_data = layers["data"].get(layer_name)
            if layer_data is None:
                continue

            df = _ensure_polars(layer_data)
            if df is None:
                continue

            # Find ID column
            local_id_col = _first_id_column(df.columns)
            if local_id_col is None:
                continue

            # Find category/element column
            known_cat_cols = ["category", "habitat", "sector", "producto", "spp", "species"]
            cat_candidates = [c for c in df.columns if c.lower() in known_cat_cols]
            if cat_candidates:
                cat_col = cat_candidates[0]
            else:
                non_numeric_cols = [
                    c
                    for c in df.columns
                    if c not in {local_id_col, "year"} and c not in df.select(cs.numeric()).columns
                ]
                if not non_numeric_cols:
                    continue
                cat_col = non_numeric_cols[0]

            # Find value column
            known_val_cols = ["val_num", "value", "weight", "boolean", "area_km2", "score"]
            val_candidates = [c for c in df.columns if c.lower() in known_val_cols]
            if val_candidates:
                val_col = val_candidates[0]
            else:
                val_col = _first_numeric_column(df, {local_id_col, "year"})
                if val_col is None:
                    continue

            df = (
                df.select([local_id_col, cat_col, val_col])
                .rename({local_id_col: "region_id", cat_col: "element", val_col: "element_wt"})
                .with_columns(pl.lit(layer_name).alias("layer"))
            )
            p_element_layers_list.append(df)

        if p_element_layers_list:
            p_element_layers = (
                pl.concat(p_element_layers_list, how="vertical_relaxed")
                .filter(pl.col("region_id").is_in(regions_vector))
                .filter(pl.col("element").is_not_null())
                .filter(pl.col("element_wt").is_not_null())
                .join(p_element_df, on="layer", how="inner")
                .select(["region_id", "goal", "element", "element_wt"])
                .with_columns(pl.col("element").cast(pl.String))
            )

            calc_pressure = calc_pressure.join(
                p_element_layers,
                on=["region_id", "goal", "element"],
                how="left",
            )
        else:
            calc_pressure = calc_pressure.with_columns(pl.lit(None).alias("element_wt"))

        goals_with_elements = p_element_df.get_column("goal").unique().to_list()

        calc_pressure = calc_pressure.filter(
            ~(pl.col("element_wt").is_null() & pl.col("goal").is_in(goals_with_elements))
        )

        calc_pressure = (
            calc_pressure.with_columns(
                pl.col("element_wt").cast(pl.Float64, strict=False).fill_null(1)
            )
            .with_columns((pl.col("pressure") * pl.col("element_wt")).alias("_weighted"))
            .group_by(["goal", "region_id"])
            .agg(
                [
                    pl.col("_weighted").sum().alias("_weighted_sum"),
                    pl.col("element_wt").sum().alias("_weight_sum"),
                ]
            )
            .with_columns(
                pl.when(pl.col("_weight_sum") == 0)
                .then(None)
                .otherwise(pl.col("_weighted_sum") / pl.col("_weight_sum"))
                .alias("pressure")
            )
            .select(["goal", "region_id", "pressure"])
        )

    # Merge with regions and format output
    scores = (
        regions_df.join(calc_pressure, on="region_id", how="left")
        .with_columns(pl.lit("pressures").alias("dimension"))
        .select(["goal", "dimension", "region_id", pl.col("pressure").alias("score")])
        .with_columns((pl.col("score") * 100).round(2).alias("score"))
        .filter(pl.col("score").is_not_null())
    )

    return scores
