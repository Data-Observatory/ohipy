"""ICO Goal - Iconic Species (Polars-native)

Status: mean of status per region × 100
Trend: mean of trend per region
"""

from __future__ import annotations

from typing import cast

import polars as pl


def ICO(layers: dict[str, object]) -> tuple[pl.DataFrame, pl.DataFrame]:  # noqa: N802
    """Calculate ICO (Iconic Species) goal status and trend.

    Returns:
        tuple: (status_df, trend_df) polars DataFrames
    """
    data_layers = cast(dict[str, object], layers["data"])

    status_layer = cast(pl.DataFrame | None, data_layers.get("ico_status"))
    if status_layer is None:
        raise ValueError("Missing layer: ico_status")

    trend_layer = cast(pl.DataFrame | None, data_layers.get("ico_trend"))
    if trend_layer is None:
        raise ValueError("Missing layer: ico_trend")

    lyr1 = status_layer.rename({"rgn_id": "region_id", "specie": "Specie"}).select(
        ["region_id", "Specie", "status"]
    )

    lyr2 = trend_layer.rename({"rgn_id": "region_id", "specie": "Specie"}).select(
        ["region_id", "Specie", "trend"]
    )

    rk = lyr1.join(lyr2, on=["region_id", "Specie"], how="inner")

    r_status = (
        rk.group_by("region_id")
        .agg(pl.col("status").mean().alias("status_mean"))
        .with_columns(
            [(pl.col("status_mean") * 100).alias("score"), pl.lit("status").alias("dimension")]
        )
        .select(["region_id", "score", "dimension"])
    )

    r_trend = (
        rk.group_by("region_id")
        .agg(pl.col("trend").cast(pl.Float32).mean().alias("score"))
        .with_columns(pl.lit("trend").alias("dimension"))
        .select(["region_id", "score", "dimension"])
    )

    return r_status, r_trend
