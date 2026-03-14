"""SPP Goal - Species (Polars-native)

Uses pre-calculated status and trend values from data layers.
"""

import polars as pl


def SPP(layers):
    """Calculate SPP (Species) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) polars DataFrames with columns:
               [region_id, score, dimension]
    """
    status_layer = layers["data"].get("spp_status")
    if status_layer is None:
        raise ValueError("Missing layer: spp_status")

    trend_layer = layers["data"].get("spp_trend")
    if trend_layer is None:
        raise ValueError("Missing layer: spp_trend")

    r_status = (
        status_layer.rename({"rgn_id": "region_id"})
        .select(["region_id", "score"])
        .with_columns(pl.lit("status").alias("dimension"))
    )

    r_trend = (
        trend_layer.rename({"rgn_id": "region_id"})
        .select(["region_id", "score"])
        .with_columns(pl.lit("trend").alias("dimension"))
    )

    return r_status, r_trend
