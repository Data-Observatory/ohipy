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


def _ensure_pandas(df):
    """Convert polars DataFrame to pandas if needed, pass through pandas unchanged."""
    if df is None:
        return None
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    return df


def MAR(layers):
    """
    Calculate MAR (Mariculture) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    # Import here to avoid circular imports
    from ohipy.calculate import calculate_trend

    # Get scenario year from layers data
    scen_year = layers["data"].get("scenario_year", 2024)

    # STEP 1: Load sustainability scores
    mar_sust_layer = _ensure_pandas(layers["data"].get("mar_sustainability_scores"))
    if mar_sust_layer is None:
        raise ValueError("Missing layer: mar_sustainability_scores")

    mar_sust = mar_sust_layer.copy()
    # Columns: especie, coeff
    mar_sust = mar_sust.rename(columns={"especie": "species", "coeff": "sust_coeff"})
    mar_sust = mar_sust[["species", "sust_coeff"]]

    # Normalize sustainability coefficient (R line 202)
    mar_sust["sust_coeff"] = mar_sust["sust_coeff"] / 10

    # STEP 2: Load harvest data
    mar_harvest_layer = _ensure_pandas(layers["data"].get("mar_harvest_tonnes"))
    if mar_harvest_layer is None:
        raise ValueError("Missing layer: mar_harvest_tonnes")

    mar_harvest = mar_harvest_layer.copy()
    # Columns: rgn_id, year, especie, tonnes
    mar_harvest = mar_harvest.rename(columns={"especie": "species"})
    mar_harvest = mar_harvest[["rgn_id", "species", "year", "tonnes"]]

    # STEP 3: Merge harvest and sustainability
    c1 = mar_harvest.merge(mar_sust, on="species", how="outer")

    # STEP 4: Calculate 4-year rolling mean (R lines 207-212)
    # Sort by rgn_id, species, year
    c2 = c1.sort_values(["rgn_id", "species", "year"])

    # Calculate rolling mean with window=4, align='right', partial=True
    # (partial=True means use available data for windows smaller than 4)
    c2["sm_tonnes"] = c2.groupby(["rgn_id", "species"])["tonnes"].transform(
        lambda x: x.rolling(window=4, min_periods=1).mean()
    )

    # STEP 5: Calculate reference point (R lines 214-220)
    # For each region-species: get max of smoothed tonnes
    pto_ref = c2.groupby(["rgn_id", "species"])["sm_tonnes"].max().reset_index()
    pto_ref = pto_ref.rename(columns={"sm_tonnes": "pto_max"})

    # For each region: sum all pto_max values
    pto_ref = pto_ref.groupby("rgn_id")["pto_max"].sum().reset_index()
    pto_ref = pto_ref.rename(columns={"pto_max": "pto_ref"})

    # Multiply by 0.01 (1% of maximum)
    pto_ref["Punto_ref"] = pto_ref["pto_ref"] * 0.01
    pto_ref = pto_ref[["rgn_id", "Punto_ref"]]

    # STEP 6: Calculate status (R lines 222-237)
    # Filter to last 5 years
    trend_years = list(range(scen_year - 4, scen_year + 1))
    c3 = c2[c2["year"].isin(trend_years)].copy()

    # Calculate mult = smoothed tonnes × sustainability coefficient
    c3["mult"] = c3["sm_tonnes"] * c3["sust_coeff"]

    # Sum mult per region-year to get YC (yield capacity)
    c3 = c3.groupby(["rgn_id", "year"])["mult"].sum().reset_index()
    c3 = c3.rename(columns={"mult": "YC"})

    # Remove duplicates (R line 230)
    c3 = c3.drop_duplicates()

    # Merge with reference point
    c4 = c3.merge(pto_ref, on="rgn_id", how="left")

    # Calculate status
    status = c4.copy()
    status["status"] = status["YC"] / status["Punto_ref"]
    status = status[["rgn_id", "year", "status"]]

    # STEP 7: Extract status for scenario year (R lines 240-243)
    status_a = status[status["year"] == scen_year].copy()
    status_a["dimension"] = "status"
    status_a = status_a.rename(columns={"rgn_id": "region_id", "status": "score"})
    status_a = status_a[["region_id", "score", "dimension"]]

    # STEP 8: Calculate trend (R lines 246-248)
    trend_df = calculate_trend(status_data=status, trend_years=trend_years, default_trend=None)

    return status_a, trend_df
