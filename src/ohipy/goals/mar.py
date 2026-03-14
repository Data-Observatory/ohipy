"""MAR Goal - Mariculture

Calculates status and trend for the Mariculture goal based on harvest and sustainability.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 191-256):
1. Load sustainability scores and harvest tonnage data
2. Normalize sustainability coefficients (divide by 10)
3. Calculate 4-year rolling mean of harvest tonnage
4. Calculate reference point: max rolling mean per species (summed per region) × 0.01
5. Calculate status: (smoothed harvest × sustainability) / reference point
6. Calculate trend using linear regression
"""

import polars as pl


def MAR(layers):
    """
    Calculate MAR (Mariculture) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a polars DataFrame with columns:
               [region_id, score, dimension]
    """
    # Import here to avoid circular imports
    from ohipy.calculate import calculate_trend

    # Get scenario year from layers data
    scen_year = layers["data"].get("scenario_year", 2024)

    # STEP 1: Load sustainability scores
    mar_sust_layer = layers["data"].get("mar_sustainability_scores")
    if mar_sust_layer is None:
        raise ValueError("Missing layer: mar_sustainability_scores")

    # Convert to polars if needed
    if hasattr(mar_sust_layer, "to_pandas"):
        mar_sust = mar_sust_layer.clone()
    else:
        mar_sust = pl.from_pandas(mar_sust_layer)

    # Columns: especie, coeff
    mar_sust = mar_sust.rename({"especie": "species", "coeff": "sust_coeff"})
    mar_sust = mar_sust.select(["species", "sust_coeff"])

    # Normalize sustainability coefficient (R line 202)
    mar_sust = mar_sust.with_columns((pl.col("sust_coeff") / 10).alias("sust_coeff"))

    # STEP 2: Load harvest data
    mar_harvest_layer = layers["data"].get("mar_harvest_tonnes")
    if mar_harvest_layer is None:
        raise ValueError("Missing layer: mar_harvest_tonnes")

    # Convert to polars if needed
    if hasattr(mar_harvest_layer, "to_pandas"):
        mar_harvest = mar_harvest_layer.clone()
    else:
        mar_harvest = pl.from_pandas(mar_harvest_layer)

    # Columns: rgn_id, year, especie, tonnes
    mar_harvest = mar_harvest.rename({"especie": "species"})
    mar_harvest = mar_harvest.select(["rgn_id", "species", "year", "tonnes"])

    # STEP 3: Merge harvest and sustainability
    c1 = mar_harvest.join(mar_sust, on="species", how="full")

    # STEP 4: Calculate 4-year rolling mean (R lines 207-212)
    # Sort by rgn_id, species, year
    c2 = c1.sort(["rgn_id", "species", "year"])

    # Calculate rolling mean with window=4, min_periods=1
    # (min_periods=1 means use available data for windows smaller than 4)
    c2 = c2.with_columns(
        pl.col("tonnes")
        .rolling_mean(window_size=4, min_periods=1)
        .over(["rgn_id", "species"])
        .alias("sm_tonnes")
    )

    # STEP 5: Calculate reference point (R lines 214-220)
    # For each region-species: get max of smoothed tonnes
    pto_ref = c2.group_by(["rgn_id", "species"]).agg(pl.col("sm_tonnes").max().alias("pto_max"))

    # For each region: sum all pto_max values
    pto_ref = pto_ref.group_by("rgn_id").agg(pl.col("pto_max").sum().alias("pto_ref"))

    # Multiply by 0.01 (1% of maximum)
    pto_ref = pto_ref.with_columns((pl.col("pto_ref") * 0.01).alias("Punto_ref"))
    pto_ref = pto_ref.select(["rgn_id", "Punto_ref"])

    # STEP 6: Calculate status (R lines 222-237)
    # Filter to last 5 years
    trend_years = list(range(scen_year - 4, scen_year + 1))
    c3 = c2.filter(pl.col("year").is_in(trend_years))

    # Calculate mult = smoothed tonnes × sustainability coefficient
    c3 = c3.with_columns((pl.col("sm_tonnes") * pl.col("sust_coeff")).alias("mult"))

    # Sum mult per region-year to get YC (yield capacity)
    c3 = c3.group_by(["rgn_id", "year"]).agg(pl.col("mult").sum().alias("YC"))

    # Remove duplicates (R line 230)
    c3 = c3.unique(subset=["rgn_id", "year"])

    # Merge with reference point
    c4 = c3.join(pto_ref, on="rgn_id", how="left")

    # Calculate status
    status = c4.with_columns((pl.col("YC") / pl.col("Punto_ref")).alias("status"))
    status = status.select(["rgn_id", "year", "status"])

    # STEP 7: Extract status for scenario year (R lines 240-243)
    status_a = status.filter(pl.col("year") == scen_year)
    status_a = status_a.with_columns(pl.lit("status").alias("dimension"))
    status_a = status_a.rename({"rgn_id": "region_id", "status": "score"})
    status_a = status_a.select(["region_id", "score", "dimension"])

    # STEP 8: Calculate trend (R lines 246-248)
    trend_df = calculate_trend(status_data=status, trend_years=trend_years, default_trend=None)

    return status_a, trend_df
