"""Resilience dimension calculator for OHI."""

from typing import Any

import polars as pl


def _to_polars(df: Any) -> pl.DataFrame | None:
    if df is None:
        return None
    if isinstance(df, pl.DataFrame):
        return df
    if isinstance(df, pl.LazyFrame):
        return df.collect()
    return pl.from_pandas(df)


def _to_polars_required(df: Any, name: str) -> pl.DataFrame:
    pl_df = _to_polars(df)
    if pl_df is None:
        raise ValueError(f"Missing layer/dataframe: {name}")
    return pl_df


def calculate_resilience_all(config, layers):
    """
    Calculate resilience scores for all goals across all regions.

    Translates ohicore/R/CalculateResilienceAll.R

    Args:
        config: Configuration dictionary from load_config()
        layers: Layers dictionary from load_layers()

    Returns:
        DataFrame with columns: goal, dimension, region_id, score
    """
    numeric_dtypes = {
        pl.Int8,
        pl.Int16,
        pl.Int32,
        pl.Int64,
        pl.UInt8,
        pl.UInt16,
        pl.UInt32,
        pl.UInt64,
        pl.Float32,
        pl.Float64,
        pl.Boolean,
    }
    string_like_dtypes = {pl.String, pl.Categorical, pl.Enum}

    # Load resilience matrix
    r_matrix = _to_polars_required(config["resilience_matrix"], "resilience_matrix").clone()

    # Reshape matrix from wide to long format
    id_cols = ["goal", "element", "element_name"]
    layer_cols = [c for c in r_matrix.columns if c not in id_cols]

    r_matrix = r_matrix.unpivot(
        index=id_cols,
        on=layer_cols,
        variable_name="layer",
        value_name="w_resilience",
    )

    # Filter out NA/null weights (in R it checks !is.na(w_resilience))
    # In the CSV, X usually marks inclusion.
    # The R code typically converts 'X' or values to usage.
    # Let's check R implementation detail:
    # r_matrix <- conf$resilience_matrix %>% tidyr::gather(...) %>% dplyr::filter(!is.na(w_resilience))
    # It seems to keep everything that is not NA.
    # If the matrix has empty strings for non-included layers?
    r_matrix = r_matrix.filter(pl.col("w_resilience").is_not_null())
    # Also ignore empty strings if any
    r_matrix = r_matrix.filter(pl.col("w_resilience") != "")

    r_matrix = r_matrix.select(["goal", "element", "layer"])

    # Fill NA element with empty string to avoid groupby dropna=True excluding them
    r_matrix = r_matrix.with_columns(pl.col("element").fill_null("").alias("element"))

    # Load resilience categories
    r_categories = _to_polars_required(
        config["resilience_categories"], "resilience_categories"
    ).clone()

    # Get resilience element mappings
    # Corrected config access
    r_element = config["config"].get("element_mappings", {}).get("resilience", {})

    if r_element:
        r_element_df = pl.DataFrame(
            [{"goal": goal, "layer": layer} for goal, layer in r_element.items()]
        )
    else:
        r_element_df = None

    # Get gamma weighting (default 0.5)
    r_gamma = config["config"]["constants"]["resilience_gamma"]

    # Get list of resilience layers
    r_layers = sorted(r_matrix.get_column("layer").unique().to_list())

    # Get regions - load region labels layer
    region_layer_name = config["config"]["layers"]["region_labels"]
    region_layer = _to_polars(layers["data"].get(region_layer_name))
    if region_layer is None:
        raise ValueError(f"Missing region layer: {region_layer_name}")

    # Extract region IDs
    id_col = [c for c in region_layer.columns if "id" in c.lower() or c == "rgn_id"][0]
    regions_df = region_layer.select(pl.col(id_col).alias("region_id"))
    regions_vector = regions_df.get_column("region_id").to_list()

    # Create ecological/social weighting for gamma
    eco_soc_weight = pl.DataFrame(
        {"category": ["ecological", "social"], "gamma_weight": [r_gamma, 1 - r_gamma]}
    )

    # Load resilience layer data - collect all layers
    # NOTE: Resilience layers usually don't have scenario years, they are static or latest year?
    # R code SelectLayersData(layers, layers=r_layers) -> typically returns all years or latest?
    # Usually resilience layers are 'static' or single year in OHI global, but let's check config.
    # If 'scenario_data_years' applies to resilience?
    # Yes, standard OHI applies scenario years if available.

    # Handle scenario data years
    scenario_data_years = _to_polars(config.get("scenario_data_years"))
    if scenario_data_years is not None and scenario_data_years.height > 0:
        scenario_data_year = scenario_data_years.clone()
        scenario_data_year = scenario_data_year.filter(pl.col("layer_name").is_in(r_layers))
        scenario_data_year = scenario_data_year.filter(
            pl.col("scenario_year") == layers["data"]["scenario_year"]
        ).select([pl.col("layer_name").alias("layer"), pl.col("data_year").alias("year")])

        # Add layers without years
        layers_no_years = set(r_layers) - set(scenario_data_year.get_column("layer").to_list())
        if layers_no_years:
            no_years_df = pl.DataFrame(
                {"layer": list(layers_no_years), "year": [20100] * len(layers_no_years)}
            )
            scenario_data_year = pl.concat([scenario_data_year, no_years_df], how="vertical")
    else:
        scenario_data_year = pl.DataFrame({"layer": r_layers, "year": [20100] * len(r_layers)})

    r_rgn_layers_list = []
    for layer_name in r_layers:
        layer_data = layers["data"].get(layer_name)
        if layer_data is None:
            continue

        df = _to_polars_required(layer_data, layer_name).clone()

        # Find ID column
        id_col = [c for c in df.columns if "id" in c.lower() or c == "rgn_id"]
        if not id_col:
            continue
        id_col = id_col[0]

        # Find value column
        # Usually val_num, value, score, or specific names
        val_col = [c for c in df.columns if c in ["val_num", "value", "resilience_score", "score"]]
        if not val_col:
            # Fallback
            val_col = [c for c in df.columns if c not in [id_col, "year", "category"]]
            if not val_col:
                continue
        val_col = val_col[0]

        # Prepare data
        cols_to_keep = [id_col, val_col]
        if "year" in df.columns:
            cols_to_keep.append("year")
            df = df.select(cols_to_keep)
        else:
            df = df.select(cols_to_keep).with_columns(pl.lit(None).alias("year"))

        df = df.rename({id_col: "region_id", val_col: "resilience_score"})

        df = df.with_columns(pl.lit(layer_name).alias("layer"))

        r_rgn_layers_list.append(df)

    if not r_rgn_layers_list:
        raise ValueError("No resilience layer data found")

    r_rgn_layers_data = pl.concat(r_rgn_layers_list, how="vertical_relaxed")

    # Filter regions
    r_rgn_layers_data = r_rgn_layers_data.filter(pl.col("region_id").is_in(regions_vector))
    r_rgn_layers_data = r_rgn_layers_data.filter(pl.col("resilience_score").is_not_null())
    r_rgn_layers_data = r_rgn_layers_data.with_columns(
        pl.col("year").fill_null(20100).alias("year")
    )

    # Join with scenario years
    r_rgn_layers = scenario_data_year.join(r_rgn_layers_data, on=["year", "layer"], how="inner")
    r_rgn_layers = r_rgn_layers.select(
        ["region_id", pl.col("resilience_score").alias("val_num"), "layer"]
    )

    # Join order matches R (lines 164-168): matrix → region data → categories
    # First merge matrix with region data (LEFT JOIN)
    rgn_matrix = r_matrix.join(r_rgn_layers, on="layer", how="left")

    # Then merge with categories (includes weight, category, category_type, subcategory)
    rgn_matrix_weights = rgn_matrix.join(r_categories, on="layer", how="left")
    # Step 1: Weighted mean by subcategory, also compute max_subcategory = max(weight)
    calc_resilience = (
        rgn_matrix_weights.with_columns(
            [
                pl.col("val_num").cast(pl.Float64).alias("val_num"),
                pl.col("weight").cast(pl.Float64).alias("weight"),
            ]
        )
        .with_columns(
            [
                (pl.col("val_num") * pl.col("weight")).alias("_weighted"),
            ]
        )
        .group_by(["goal", "element", "region_id", "category", "category_type", "subcategory"])
        .agg(
            [
                pl.col("_weighted").sum().alias("_weighted_sum"),
                pl.col("weight").sum().alias("_weight_sum"),
                pl.col("weight").max().alias("max_subcategory"),
            ]
        )
        .with_columns(
            [
                pl.when(pl.col("_weight_sum") == 0)
                .then(None)
                .otherwise(pl.col("_weighted_sum") / pl.col("_weight_sum"))
                .alias("val_num"),
            ]
        )
        .select(
            [
                "goal",
                "element",
                "region_id",
                "category",
                "category_type",
                "subcategory",
                "val_num",
                "max_subcategory",
            ]
        )
    )

    # Step 2: Weighted mean by category_type (using max_subcategory as weight)
    calc_resilience = (
        calc_resilience.with_columns(
            [
                pl.col("val_num").cast(pl.Float64).alias("val_num"),
                pl.col("max_subcategory").cast(pl.Float64).alias("max_subcategory"),
            ]
        )
        .with_columns(
            [
                (pl.col("val_num") * pl.col("max_subcategory")).alias("_weighted"),
            ]
        )
        .group_by(["goal", "element", "region_id", "category", "category_type"])
        .agg(
            [
                pl.col("_weighted").sum().alias("_weighted_sum"),
                pl.col("max_subcategory").sum().alias("_weight_sum"),
            ]
        )
        .with_columns(
            [
                pl.when((pl.col("_weight_sum") == 0) | pl.col("_weight_sum").is_null())
                .then(None)
                .otherwise(pl.col("_weighted_sum") / pl.col("_weight_sum"))
                .alias("val_num"),
            ]
        )
        .select(["goal", "element", "region_id", "category", "category_type", "val_num"])
    )

    # Step 3: Simple mean across category_types within category
    calc_resilience = calc_resilience.group_by(["goal", "element", "region_id", "category"]).agg(
        [
            pl.col("val_num").mean().alias("val_num"),
        ]
    )

    # Step 4: Combine ecological and social based on gamma weighting
    calc_resilience = (
        calc_resilience.join(eco_soc_weight, on="category", how="left")
        .with_columns(
            [
                pl.col("val_num").cast(pl.Float64).alias("val_num"),
                pl.col("gamma_weight").cast(pl.Float64).alias("gamma_weight"),
            ]
        )
        .with_columns(
            [
                (pl.col("val_num") * pl.col("gamma_weight")).alias("_weighted"),
            ]
        )
        .group_by(["goal", "element", "region_id"])
        .agg(
            [
                pl.col("_weighted").sum().alias("_weighted_sum"),
                pl.col("gamma_weight").sum().alias("_weight_sum"),
            ]
        )
        .with_columns(
            [
                pl.when(pl.col("_weight_sum") == 0)
                .then(None)
                .otherwise(pl.col("_weighted_sum") / pl.col("_weight_sum"))
                .alias("resilience"),
            ]
        )
        .select(["goal", "element", "region_id", "resilience"])
    )

    # Handle goals with elements
    if r_element_df is not None and r_element_df.height > 0:
        # Load element weight layers
        r_element_layers_list = []
        for layer_name in r_element_df.get_column("layer").unique().to_list():
            layer_data = layers["data"].get(layer_name)
            if layer_data is None:
                continue

            df = _to_polars_required(layer_data, layer_name).clone()

            # Robust column detection (reused from pressures.py)
            id_col = [c for c in df.columns if "id" in c.lower() or c == "rgn_id"]
            if not id_col:
                continue
            id_col = id_col[0]

            known_cat_cols = [
                "category",
                "habitat",
                "sector",
                "producto",
                "spp",
                "species",
            ]
            cat_col = [c for c in df.columns if c.lower() in known_cat_cols]
            if cat_col:
                cat_col = cat_col[0]
            else:
                obj_cols = [c for c, dtype in df.schema.items() if dtype in string_like_dtypes]
                obj_cols = [c for c in obj_cols if c != id_col and c != "year"]
                if obj_cols:
                    cat_col = obj_cols[0]
                else:
                    continue

            known_val_cols = [
                "val_num",
                "value",
                "weight",
                "boolean",
                "area_km2",
                "score",
            ]
            val_col = [c for c in df.columns if c.lower() in known_val_cols]
            if val_col:
                val_col = val_col[0]
            else:
                num_cols = [c for c, dtype in df.schema.items() if dtype in numeric_dtypes]
                num_cols = [c for c in num_cols if c != id_col and c != "year"]
                if num_cols:
                    val_col = num_cols[0]
                else:
                    continue

            df = df.select([id_col, cat_col, val_col])
            df = df.rename({id_col: "region_id", cat_col: "element", val_col: "element_wt"})
            df = df.with_columns(pl.lit(layer_name).alias("layer"))
            r_element_layers_list.append(df)

        if r_element_layers_list:
            r_element_layers = pl.concat(r_element_layers_list, how="vertical_relaxed")
            r_element_layers = r_element_layers.filter(pl.col("region_id").is_in(regions_vector))
            r_element_layers = r_element_layers.filter(pl.col("element").is_not_null())
            r_element_layers = r_element_layers.filter(pl.col("element_wt").is_not_null())

            r_element_layers = r_element_layers.join(r_element_df, on="layer", how="inner")
            r_element_layers = r_element_layers.select(
                ["region_id", "goal", "element", "element_wt"]
            )
            r_element_layers = r_element_layers.with_columns(
                pl.col("element").cast(pl.String).alias("element")
            )

            calc_resilience = calc_resilience.join(
                r_element_layers, on=["region_id", "goal", "element"], how="left"
            )
        else:
            calc_resilience = calc_resilience.with_columns(pl.lit(None).alias("element_wt"))

        goals_with_elements = r_element_df.get_column("goal").unique().to_list()

        calc_resilience = calc_resilience.filter(
            ~(pl.col("element_wt").is_null() & pl.col("goal").is_in(goals_with_elements))
        )

        calc_resilience = calc_resilience.with_columns(
            pl.col("element_wt").fill_null(1).alias("element_wt")
        )

        # Calculate weighted mean of elements using Polars expressions
        calc_resilience = (
            calc_resilience.with_columns(
                [
                    pl.col("element_wt").cast(pl.Float64).alias("element_wt"),
                    pl.col("resilience").cast(pl.Float64).alias("resilience"),
                ]
            )
            .with_columns(
                [
                    (pl.col("resilience") * pl.col("element_wt")).alias("_weighted"),
                ]
            )
            .group_by(["goal", "region_id"])
            .agg(
                [
                    pl.col("_weighted").sum().alias("_weighted_sum"),
                    pl.col("element_wt").sum().alias("_weight_sum"),
                ]
            )
            .with_columns(
                [
                    pl.when(pl.col("_weight_sum") == 0)
                    .then(None)
                    .otherwise(pl.col("_weighted_sum") / pl.col("_weight_sum"))
                    .alias("resilience"),
                ]
            )
            .select(["goal", "region_id", "resilience"])
        )

    # Merge with regions and format output
    scores = regions_df.join(calc_resilience, on="region_id", how="left")
    scores = scores.with_columns(pl.lit("resilience").alias("dimension"))
    scores = scores.select(["goal", "dimension", "region_id", pl.col("resilience").alias("score")])
    scores = scores.with_columns((pl.col("score") * 100).round(2).alias("score"))

    return scores
