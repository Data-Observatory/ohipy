"""SPP Goal - Species (Polars-native)

Uses pre-calculated status and trend values from data layers.
"""

from __future__ import annotations

from typing import cast

import polars as pl


def SPP(layers: dict[str, object]) -> tuple[pl.DataFrame, pl.DataFrame]:  # noqa: N802
    """Calculate SPP (Species) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) polars DataFrames with columns:
               [region_id, score, dimension]
    """
    data_layers = cast(dict[str, object], layers["data"])

    status_layer = cast(pl.DataFrame | None, data_layers.get("spp_status"))
    if status_layer is None:
        raise ValueError("Missing layer: spp_status")

    trend_layer = cast(pl.DataFrame | None, data_layers.get("spp_trend"))
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
