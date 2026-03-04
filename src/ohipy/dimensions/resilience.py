"""Resilience dimension calculator for OHI."""

import pandas as pd
import numpy as np


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
    # Load resilience matrix
    r_matrix = config["resilience_matrix"].copy()

    # Reshape matrix from wide to long format
    id_cols = ["goal", "element", "element_name"]
    layer_cols = [c for c in r_matrix.columns if c not in id_cols]

    r_matrix = r_matrix.melt(
        id_vars=id_cols,
        value_vars=layer_cols,
        var_name="layer",
        value_name="w_resilience",
    )

    # Filter out NA/null weights (in R it checks !is.na(w_resilience))
    # In the CSV, X usually marks inclusion.
    # The R code typically converts 'X' or values to usage.
    # Let's check R implementation detail:
    # r_matrix <- conf$resilience_matrix %>% tidyr::gather(...) %>% dplyr::filter(!is.na(w_resilience))
    # It seems to keep everything that is not NA.
    # If the matrix has empty strings for non-included layers?
    r_matrix = r_matrix[r_matrix["w_resilience"].notna()]
    # Also ignore empty strings if any
    r_matrix = r_matrix[r_matrix["w_resilience"] != ""]

    r_matrix = r_matrix[["goal", "element", "layer"]]

    # Fill NA element with empty string to avoid groupby dropna=True excluding them
    r_matrix["element"] = r_matrix["element"].fillna("")

    # Load resilience categories
    r_categories = config["resilience_categories"].copy()

    # Get resilience element mappings
    # Corrected config access
    r_element = config["config"].get("element_mappings", {}).get("resilience", {})

    if r_element:
        r_element_df = pd.DataFrame(
            [{"goal": goal, "layer": layer} for goal, layer in r_element.items()]
        )
    else:
        r_element_df = None

    # Get gamma weighting (default 0.5)
    r_gamma = config["config"]["constants"]["resilience_gamma"]

    # Get list of resilience layers
    r_layers = sorted(r_matrix["layer"].unique())

    # Get regions - load region labels layer
    region_layer_name = config["config"]["layers"]["region_labels"]
    region_layer = layers["data"].get(region_layer_name)
    if region_layer is None:
        raise ValueError(f"Missing region layer: {region_layer_name}")

    # Extract region IDs
    id_col = [c for c in region_layer.columns if "id" in c.lower() or c == "rgn_id"][0]
    regions_df = region_layer[[id_col]].copy().rename(columns={id_col: "region_id"})
    regions_vector = regions_df["region_id"].tolist()

    # Create ecological/social weighting for gamma
    eco_soc_weight = pd.DataFrame(
        {"category": ["ecological", "social"], "gamma_weight": [r_gamma, 1 - r_gamma]}
    )

    # Load resilience layer data - collect all layers
    # NOTE: Resilience layers usually don't have scenario years, they are static or latest year?
    # R code SelectLayersData(layers, layers=r_layers) -> typically returns all years or latest?
    # Usually resilience layers are 'static' or single year in OHI global, but let's check config.
    # If 'scenario_data_years' applies to resilience?
    # Yes, standard OHI applies scenario years if available.

    # Handle scenario data years
    if "scenario_data_years" in config and len(config["scenario_data_years"]) > 0:
        scenario_data_year = config["scenario_data_years"].copy()
        scenario_data_year = scenario_data_year[
            scenario_data_year["layer_name"].isin(r_layers)
        ]
        scenario_data_year = scenario_data_year[
            scenario_data_year["scenario_year"] == layers["data"]["scenario_year"]
        ][["layer_name", "data_year"]].rename(
            columns={"layer_name": "layer", "data_year": "year"}
        )

        # Add layers without years
        layers_no_years = set(r_layers) - set(scenario_data_year["layer"])
        if layers_no_years:
            no_years_df = pd.DataFrame({"layer": list(layers_no_years), "year": 20100})
            scenario_data_year = pd.concat(
                [scenario_data_year, no_years_df], ignore_index=True
            )
    else:
        scenario_data_year = pd.DataFrame({"layer": r_layers, "year": 20100})

    r_rgn_layers_list = []
    for layer_name in r_layers:
        layer_data = layers["data"].get(layer_name)
        if layer_data is None:
            continue

        df = layer_data.copy()

        # Find ID column
        id_col = [c for c in df.columns if "id" in c.lower() or c == "rgn_id"]
        if not id_col:
            continue
        id_col = id_col[0]

        # Find value column
        # Usually val_num, value, score, or specific names
        val_col = [
            c
            for c in df.columns
            if c in ["val_num", "value", "resilience_score", "score"]
        ]
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
            df = df[cols_to_keep].copy()
        else:
            df = df[cols_to_keep].copy()
            df["year"] = np.nan

        df = df.rename(columns={id_col: "region_id", val_col: "resilience_score"})

        df["layer"] = layer_name

        r_rgn_layers_list.append(df)

    if not r_rgn_layers_list:
        raise ValueError("No resilience layer data found")

    r_rgn_layers_data = pd.concat(r_rgn_layers_list, ignore_index=True)

    # Filter regions
    r_rgn_layers_data = r_rgn_layers_data[
        r_rgn_layers_data["region_id"].isin(regions_vector)
    ]
    r_rgn_layers_data = r_rgn_layers_data[r_rgn_layers_data["resilience_score"].notna()]
    r_rgn_layers_data["year"] = r_rgn_layers_data["year"].fillna(20100)

    # Join with scenario years
    r_rgn_layers = scenario_data_year.merge(r_rgn_layers_data, on=["year", "layer"])
    r_rgn_layers = r_rgn_layers[["region_id", "resilience_score", "layer"]].rename(
        columns={"resilience_score": "val_num"}
    )

    # Join order matches R (lines 164-168): matrix → region data → categories
    # First merge matrix with region data (LEFT JOIN)
    rgn_matrix = r_matrix.merge(r_rgn_layers, on="layer", how="left")

    # Then merge with categories (includes weight, category, category_type, subcategory)
    rgn_matrix_weights = rgn_matrix.merge(r_categories, on="layer", how="left")

    # R's 3-step aggregation process (vectorized for performance)
    # Step 1: Weighted mean by subcategory, also compute max_subcategory = max(weight)
    rgn_matrix_weights["_weighted"] = rgn_matrix_weights["val_num"].astype(float) * rgn_matrix_weights["weight"].astype(float)
    calc_resilience = (
        rgn_matrix_weights.groupby(
            ["goal", "element", "region_id", "category", "category_type", "subcategory"]
        )
        .agg(
            _weighted_sum=("_weighted", "sum"),
            _weight_sum=("weight", lambda x: x.astype(float).sum()),
            max_subcategory=("weight", lambda x: x.astype(float).max()),
        )
        .reset_index()
    )
    # Avoid division by zero
    calc_resilience["val_num"] = np.where(
        calc_resilience["_weight_sum"] == 0,
        np.nan,
        calc_resilience["_weighted_sum"] / calc_resilience["_weight_sum"],
    )
    calc_resilience = calc_resilience[["goal", "element", "region_id", "category", "category_type", "subcategory", "val_num", "max_subcategory"]]

    # Step 2: Weighted mean by category_type (using max_subcategory as weight) - vectorized
    calc_resilience["_weighted"] = calc_resilience["val_num"].astype(float) * calc_resilience["max_subcategory"].astype(float)
    calc_resilience = (
        calc_resilience.groupby(["goal", "element", "region_id", "category", "category_type"])
        .agg(_weighted_sum=("_weighted", "sum"), _weight_sum=("max_subcategory", lambda x: x.astype(float).sum()))
        .reset_index()
    )
    # Avoid division by zero - also handle all-NaN weights
    mask = (calc_resilience["_weight_sum"] == 0) | (calc_resilience["_weight_sum"].isna())
    calc_resilience["val_num"] = np.where(
        mask,
        np.nan,
        calc_resilience["_weighted_sum"] / calc_resilience["_weight_sum"],
    )
    calc_resilience = calc_resilience[["goal", "element", "region_id", "category", "category_type", "val_num"]]

    # Step 3: Simple mean across category_types within category
    calc_resilience = (
        calc_resilience.groupby(["goal", "element", "region_id", "category"])["val_num"]
        .mean()
        .reset_index()
    )

    # Step 4: Combine ecological and social based on gamma weighting - vectorized
    calc_resilience = calc_resilience.merge(eco_soc_weight, on="category")
    calc_resilience["_weighted"] = calc_resilience["val_num"].astype(float) * calc_resilience["gamma_weight"].astype(float)
    calc_resilience = (
        calc_resilience.groupby(["goal", "element", "region_id"])
        .agg(_weighted_sum=("_weighted", "sum"), _weight_sum=("gamma_weight", lambda x: x.astype(float).sum()))
        .reset_index()
    )
    # Avoid division by zero
    calc_resilience["resilience"] = np.where(
        calc_resilience["_weight_sum"] == 0,
        np.nan,
        calc_resilience["_weighted_sum"] / calc_resilience["_weight_sum"],
    )
    calc_resilience = calc_resilience[["goal", "element", "region_id", "resilience"]]

    # Handle goals with elements
    if r_element_df is not None and len(r_element_df) > 0:
        # Load element weight layers
        r_element_layers_list = []
        for layer_name in r_element_df["layer"].unique():
            layer_data = layers["data"].get(layer_name)
            if layer_data is None:
                continue

            df = layer_data.copy()

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
                obj_cols = [
                    c
                    for c in df.columns
                    if df[c].dtype == "object" or df[c].dtype == "string"
                ]
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
                num_cols = [
                    c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])
                ]
                num_cols = [c for c in num_cols if c != id_col and c != "year"]
                if num_cols:
                    val_col = num_cols[0]
                else:
                    continue

            df = df[[id_col, cat_col, val_col]].copy()
            df = df.rename(
                columns={id_col: "region_id", cat_col: "element", val_col: "element_wt"}
            )
            df["layer"] = layer_name
            r_element_layers_list.append(df)

        if r_element_layers_list:
            r_element_layers = pd.concat(r_element_layers_list, ignore_index=True)
            r_element_layers = r_element_layers[
                r_element_layers["region_id"].isin(regions_vector)
            ]
            r_element_layers = r_element_layers[r_element_layers["element"].notna()]
            r_element_layers = r_element_layers[r_element_layers["element_wt"].notna()]

            r_element_layers = r_element_layers.merge(r_element_df, on="layer")
            r_element_layers = r_element_layers[
                ["region_id", "goal", "element", "element_wt"]
            ]
            r_element_layers["element"] = r_element_layers["element"].astype(str)

            calc_resilience = calc_resilience.merge(
                r_element_layers, on=["region_id", "goal", "element"], how="left"
            )
        else:
            calc_resilience["element_wt"] = np.nan

        goals_with_elements = r_element_df["goal"].unique()

        calc_resilience = calc_resilience[
            ~(
                (calc_resilience["element_wt"].isna())
                & (calc_resilience["goal"].isin(goals_with_elements))
            )
        ]

        calc_resilience["element_wt"] = calc_resilience["element_wt"].fillna(1)

        def weighted_mean_element(group):
            weights = group["element_wt"].astype(float)
            values = group["resilience"].astype(float)
            if weights.sum() == 0:
                return np.nan
            return np.average(values, weights=weights)

        calc_resilience = (
            calc_resilience.groupby(["goal", "region_id"])
            .apply(weighted_mean_element, include_groups=False)
            .reset_index(name="resilience")
        )

    # Merge with regions and format output
    scores = regions_df.merge(calc_resilience, on="region_id", how="left")
    scores["dimension"] = "resilience"
    scores = scores[["goal", "dimension", "region_id", "resilience"]].rename(
        columns={"resilience": "score"}
    )
    scores["score"] = (scores["score"] * 100).round(2)

    return scores
