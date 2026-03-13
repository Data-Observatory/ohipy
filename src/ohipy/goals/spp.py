"""SPP Goal - Species

Calculates status and trend for the Species goal.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 1275-1294):
1. Load spp_status layer (pre-calculated status values)
2. Load spp_trend layer (pre-calculated trend values)
3. Return status and trend dataframes
"""

import pandas as pd


def _ensure_pandas(df):
    """Convert polars DataFrame to pandas if needed, pass through pandas unchanged."""
    if df is None:
        return None
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    return df


def SPP(layers):
    """
    Calculate SPP (Species) goal status and trend.

    This goal uses pre-calculated status and trend values from data layers.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    # STEP 1: Load status scores
    spp_status_layer = layers["data"].get("spp_status")
    spp_status_layer = _ensure_pandas(spp_status_layer)
    if spp_status_layer is None:
        raise ValueError("Missing layer: spp_status")

    spp_status = spp_status_layer.copy()
    # Columns: rgn_id, score
    spp_status = spp_status.rename(columns={"rgn_id": "region_id"})

    # Status: Return [region_id, score, dimension='status']
    r_status = spp_status[["region_id", "score"]].copy()
    r_status["dimension"] = "status"

    # STEP 2: Load trend scores
    spp_trend_layer = layers["data"].get("spp_trend")
    spp_trend_layer = _ensure_pandas(spp_trend_layer)
    if spp_trend_layer is None:
        raise ValueError("Missing layer: spp_trend")

    spp_trend = spp_trend_layer.copy()
    # Columns: rgn_id, score, dimension, goal
    spp_trend = spp_trend.rename(columns={"rgn_id": "region_id"})

    # Trend: Return [region_id, score, dimension='trend']
    r_trend = spp_trend[["region_id", "score"]].copy()
    r_trend["dimension"] = "trend"

    return r_status, r_trend
