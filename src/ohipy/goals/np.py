"""NP Goal - Natural Products

Calculates status and trend for the Natural Products goal based on harvest data.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 329-433):
1. Load harvest tonnes, relative tonnes, weights, and sustainability coefficients
2. Merge all data layers
3. Calculate product scores: Pc = tonnes_rel × coef
4. Calculate weighted mean status per region-year
5. Extract status for scenario year
6. Calculate trend using linear regression
"""

import numpy as np
import pandas as pd


def _ensure_pandas(df):
    """Convert polars DataFrame to pandas if needed, pass through pandas unchanged."""
    if df is None:
        return None
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    return df


def NP(layers):
    """
    Calculate NP (Natural Products) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    # Import here to avoid circular imports
    from ohipy.calculate import calculate_trend

    # Get scenario year
    scen_year = layers["data"].get("scenario_year", 2024)
    trend_years = list(range(scen_year - 4, scen_year + 1))

    # STEP 1: Load harvest tonnes
    h_tonnes_layer = _ensure_pandas(layers["data"].get("np_harvest_tonnes"))
    if h_tonnes_layer is None:
        raise ValueError("Missing layer: np_harvest_tonnes")

    h_tonnes = h_tonnes_layer.copy()
    # Columns: rgn_id, producto, year, tonnes
    h_tonnes = h_tonnes.rename(columns={"producto": "Producto"})
    h_tonnes["rgn_id"] = h_tonnes["rgn_id"].astype(float)
    h_tonnes = h_tonnes[["year", "rgn_id", "Producto", "tonnes"]]

    # STEP 2: Load harvest tonnes relative
    h_tonnes_rel_layer = _ensure_pandas(layers["data"].get("np_harvest_tonnes_relative"))
    if h_tonnes_rel_layer is None:
        raise ValueError("Missing layer: np_harvest_tonnes_relative")

    h_tonnes_rel = h_tonnes_rel_layer.copy()
    # Columns: rgn_id, producto, year, tonnes_rel
    h_tonnes_rel = h_tonnes_rel.rename(columns={"producto": "Producto"})
    h_tonnes_rel["rgn_id"] = h_tonnes_rel["rgn_id"].astype(float)
    h_tonnes_rel = h_tonnes_rel[["year", "rgn_id", "Producto", "tonnes_rel"]]

    # STEP 3: Load harvest tonnes weight
    h_tonnes_w_layer = _ensure_pandas(layers["data"].get("np_harvest_tonnes_weigth"))
    if h_tonnes_w_layer is None:
        raise ValueError("Missing layer: np_harvest_tonnes_weigth")

    h_tonnes_w = h_tonnes_w_layer.copy()
    # Columns: rgn_id, year, producto, weight
    h_tonnes_w = h_tonnes_w.rename(columns={"producto": "Producto", "weight": "proportion"})
    h_tonnes_w["rgn_id"] = h_tonnes_w["rgn_id"].astype(float)
    h_tonnes_w = h_tonnes_w[["year", "rgn_id", "Producto", "proportion"]]

    # STEP 4: Load FOFM sustainability scores
    np_fofm_layer = _ensure_pandas(layers["data"].get("np_fofm_scores"))
    if np_fofm_layer is None:
        raise ValueError("Missing layer: np_fofm_scores")

    np_fofm = np_fofm_layer.copy()
    # Columns: rgn_id, year, score, producto
    np_fofm = np_fofm.rename(columns={"producto": "Producto", "score": "coef"})
    np_fofm["rgn_id"] = np_fofm["rgn_id"].astype(float)
    np_fofm = np_fofm[["year", "rgn_id", "Producto", "coef"]]

    # STEP 5: Load seaweed sustainability scores
    np_seaweed_layer = _ensure_pandas(layers["data"].get("np_seaweed_sust"))
    if np_seaweed_layer is None:
        raise ValueError("Missing layer: np_seaweed_sust")

    np_seaweed = np_seaweed_layer.copy()
    # Columns: rgn_id, producto, year, score
    np_seaweed = np_seaweed.rename(columns={"producto": "Producto", "score": "coef"})
    np_seaweed["rgn_id"] = np_seaweed["rgn_id"].astype(float)
    np_seaweed = np_seaweed[["year", "rgn_id", "Producto", "coef"]]

    # STEP 6: Merge harvest data
    np_harvest = h_tonnes_w.merge(h_tonnes, on=["year", "rgn_id", "Producto"], how="outer")
    np_harvest = np_harvest.merge(h_tonnes_rel, on=["year", "rgn_id", "Producto"], how="outer")

    # STEP 7: Combine sustainability scores
    np_sust = pd.concat([np_fofm, np_seaweed], ignore_index=True)

    # STEP 8: Merge harvest with sustainability
    np_harvest = np_harvest.merge(np_sust, on=["year", "rgn_id", "Producto"], how="outer")

    # STEP 9: Calculate product scores
    np_status_all = np_harvest.copy()
    np_status_all["Pc"] = np_status_all["tonnes_rel"] * np_status_all["coef"]

    # STEP 10: Filter to last 5 years and non-NA tonnes
    np_status_all = np_status_all[
        (~np_status_all["tonnes"].isna()) & (np_status_all["year"].isin(trend_years))
    ]

    # STEP 11: Fill missing proportions with 1
    np_status_all["proportion"] = np_status_all["proportion"].fillna(1)

    # STEP 12: Calculate weighted mean status per region-year
    np_status_all = (
        np_status_all.groupby(["rgn_id", "year"])
        .apply(lambda x: pd.Series({"status": np.average(x["Pc"] * x["proportion"]) * 100}))
        .reset_index()
    )

    # Remove NA status
    np_status_all = np_status_all[~np_status_all["status"].isna()]

    # STEP 13: Extract status for scenario year
    np_status_current = np_status_all[np_status_all["year"] == scen_year].copy()
    np_status_current["dimension"] = "status"
    np_status_current["score"] = np_status_current["status"].round(4)
    np_status_current = np_status_current.rename(columns={"rgn_id": "region_id"})
    np_status_current = np_status_current[["region_id", "dimension", "score"]]

    # STEP 14: Calculate trend
    np_trend = calculate_trend(
        status_data=np_status_all, trend_years=trend_years, default_trend=None
    )

    return np_status_current, np_trend
