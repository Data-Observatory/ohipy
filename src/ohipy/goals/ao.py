"""AO Goal - Artisanal Opportunities

Calculates status and trend for the Artisanal Opportunities goal.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 297-327):
1. Load ao_scores layer (pre-calculated status values)
2. Filter to scenario year for status dimension
3. Load ao_trend layer (pre-calculated trend values)
4. Combine and return
"""

import polars as pl


def AO(layers):
    """
    Calculate AO (Artisanal Opportunities) goal status and trend.

    This goal uses pre-calculated status and trend values from data layers.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a Polars DataFrame with columns:
               [region_id, score, dimension]
    """
    # Get scenario year
    scen_year = layers["data"].get("scenario_year", 2024)

    # STEP 1: Load status scores
    ao_scores_layer = layers["data"].get("ao_scores")
    if ao_scores_layer is None:
        raise ValueError("Missing layer: ao_scores")

    ao_scores = ao_scores_layer.clone()
    # Columns: rgn_id, score, year
    ao_scores = ao_scores.rename({"rgn_id": "region_id"})

    # Filter to scenario year for status
    r_status = (
        ao_scores.filter(pl.col("year") == scen_year)
        .select(["region_id", "score"])
        .with_columns(pl.lit("status").alias("dimension"))
    )

    # STEP 2: Load trend scores
    ao_trend_layer = layers["data"].get("ao_trend")
    if ao_trend_layer is None:
        raise ValueError("Missing layer: ao_trend")

    ao_trend = ao_trend_layer.clone()
    # Columns: rgn_id, year, trend
    ao_trend = (
        ao_trend.rename({"rgn_id": "region_id", "trend": "score"})
        .select(["region_id", "score"])
        .with_columns(pl.lit("trend").alias("dimension"))
    )

    return r_status, ao_trend
