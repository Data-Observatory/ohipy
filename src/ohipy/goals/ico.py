"""ICO Goal - Iconic Species

Calculates status and trend for the Iconic Species goal.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 973-1016):
1. Load ico_status and ico_trend layers
2. Merge on region_id and specie
3. Status: Mean of status per region × 100
4. Trend: Mean of trend per region
"""

import pandas as pd
import numpy as np


def _ensure_pandas(df):
    """Convert polars DataFrame to pandas if needed, pass through pandas unchanged."""
    if df is None:
        return None
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    return df


def ICO(layers):
    """
    Calculate ICO (Iconic Species) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    # STEP 1: Load ico_status layer
    ico_status_layer = _ensure_pandas(layers["data"].get("ico_status"))
    if ico_status_layer is None:
        raise ValueError("Missing layer: ico_status")

    lyr1 = ico_status_layer.copy()
    lyr1 = lyr1.rename(columns={"rgn_id": "region_id", "specie": "Specie", "status": "status"})
    lyr1 = lyr1[["region_id", "Specie", "status"]]

    # STEP 2: Load ico_trend layer
    ico_trend_layer = _ensure_pandas(layers["data"].get("ico_trend"))
    if ico_trend_layer is None:
        raise ValueError("Missing layer: ico_trend")

    lyr2 = ico_trend_layer.copy()
    lyr2 = lyr2.rename(columns={"rgn_id": "region_id", "specie": "Specie", "trend": "trend"})
    lyr2 = lyr2[["region_id", "Specie", "trend"]]

    # STEP 3: Merge the two layers
    rk = lyr1.merge(lyr2, on=["region_id", "Specie"], how="inner")

    # STEP 4: Calculate status - mean of status per region × 100
    r_status = rk.groupby("region_id").agg({"status": lambda x: x.mean()}).reset_index()
    r_status["score"] = r_status["status"] * 100
    r_status["dimension"] = "status"
    r_status = r_status[["region_id", "score", "dimension"]]

    # STEP 5: Calculate trend - mean of trend per region
    r_trend = (
        rk.groupby("region_id").agg({"trend": lambda x: np.mean(x.astype("float32"))}).reset_index()
    )
    r_trend = r_trend.rename(columns={"trend": "score"})
    r_trend["dimension"] = "trend"
    r_trend = r_trend[["region_id", "score", "dimension"]]

    return r_status, r_trend
