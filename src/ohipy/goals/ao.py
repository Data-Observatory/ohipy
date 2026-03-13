"""AO Goal - Artisanal Opportunities

Calculates status and trend for the Artisanal Opportunities goal.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 297-327):
1. Load ao_scores layer (pre-calculated status values)
2. Filter to scenario year for status dimension
3. Load ao_trend layer (pre-calculated trend values)
4. Combine and return
"""

import pandas as pd


def _ensure_pandas(df):
    """Convert polars DataFrame to pandas if needed, pass through pandas unchanged."""
    if df is None:
        return None
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    return df


def AO(layers):
    """
    Calculate AO (Artisanal Opportunities) goal status and trend.

    This goal uses pre-calculated status and trend values from data layers.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    # Get scenario year
    scen_year = layers["data"].get("scenario_year", 2024)

    # STEP 1: Load status scores
    ao_scores_layer = _ensure_pandas(layers["data"].get("ao_scores"))
    if ao_scores_layer is None:
        raise ValueError("Missing layer: ao_scores")

    ao_scores = ao_scores_layer.copy()
    # Columns: rgn_id, score, year
    ao_scores = ao_scores.rename(columns={"rgn_id": "region_id"})

    # Filter to scenario year for status
    r_status = ao_scores[ao_scores["year"] == scen_year].copy()
    r_status = r_status[["region_id", "score"]]
    r_status["dimension"] = "status"

    # STEP 2: Load trend scores
    ao_trend_layer = _ensure_pandas(layers["data"].get("ao_trend"))
    if ao_trend_layer is None:
        raise ValueError("Missing layer: ao_trend")

    ao_trend = ao_trend_layer.copy()
    # Columns: rgn_id, year, trend
    ao_trend = ao_trend.rename(columns={"rgn_id": "region_id", "trend": "score"})
    ao_trend = ao_trend[["region_id", "score"]]
    ao_trend["dimension"] = "trend"

    return r_status, ao_trend
