"""CP Goal - Coastal Protection

Calculates status and trend for the Coastal Protection goal based on habitat
extent.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 534-616):
1. Load habitat extension data for last 5 years
2. Calculate trend per region-habitat: coef(year) * sd(year) / sd(km2) * 5, clamp to [-1,1]
3. Calculate health per region-habitat: km2 / max(km2)
4. Define habitat ranks: Macrocystis=3, Bosques y matorrales=4,
   Marismas y humedales=2, Playas y dunas=1
5. Calculate f1 = rank * health * km2
6. Status: sum(f1) / (sum(km2) * max(rank)) * 100, capped at 100
7. Trend: sum(rank * trend * km2) / sum(km2 * rank)
"""

from __future__ import annotations

from typing import cast

import polars as pl


def CP(layers: dict[str, object]) -> tuple[pl.DataFrame, pl.DataFrame]:  # noqa: N802
    data_layers = cast(dict[str, object], layers["data"])
    scen_year = cast(int, data_layers.get("scenario_year", 2024))

    extent_layer = cast(pl.DataFrame | None, data_layers.get("cp_habitat_extension"))
    if extent_layer is None:
        raise ValueError("Missing layer: cp_habitat_extension")

    extent = extent_layer.clone()

    extent = extent.rename({"value": "km2"})
    extent = extent.filter(pl.col("year") >= (scen_year - 4))
    extent = extent.select(["year", "rgn_id", "habitat", "km2"])

    # TREND CALCULATION (Pure Polars - no loops)
    # slope = (n * sum(x*y) - sum(x) * sum(y)) / (n * sum(x^2) - sum(x)^2)
    # trend = slope * sd(year) / sd(km2) * 5
    trend = (
        extent.group_by(["rgn_id", "habitat"])
        .agg(
            [
                pl.len().alias("n"),
                (pl.col("year") * pl.col("km2")).sum().alias("xy_sum"),
                pl.col("year").sum().alias("x_sum"),
                pl.col("km2").sum().alias("y_sum"),
                (pl.col("year") ** 2).sum().alias("x2_sum"),
                pl.col("year").std().alias("std_year"),
                pl.col("km2").std().alias("std_km2"),
            ]
        )
        .with_columns(
            [
                (
                    (pl.col("n") * pl.col("xy_sum") - pl.col("x_sum") * pl.col("y_sum"))
                    / (pl.col("n") * pl.col("x2_sum") - pl.col("x_sum") ** 2)
                ).alias("slope")
            ]
        )
        .with_columns(
            [
                pl.when((pl.col("std_km2") == 0) | (pl.col("n") < 2))
                .then(None)
                .otherwise(
                    (pl.col("slope") * pl.col("std_year") / pl.col("std_km2") * 5).clip(-1, 1)
                )
                .alias("trend")
            ]
        )
        .select(["rgn_id", "habitat", "trend"])
    )

    # HEALTH CALCULATION
    health_agg = extent.group_by(["rgn_id", "habitat"]).agg(pl.col("km2").max().alias("km2_max"))
    health = extent.join(health_agg, on=["rgn_id", "habitat"], how="left")
    health = health.with_columns((pl.col("km2") / pl.col("km2_max")).alias("health"))

    # MERGE extent, health, trend
    d = extent.join(
        health.select(["year", "rgn_id", "habitat", "health"]),
        on=["year", "rgn_id", "habitat"],
        how="left",
    )
    d = d.join(trend, on=["rgn_id", "habitat"], how="left")

    # HABITAT RANKS
    habitat_rank = pl.DataFrame(
        {
            "habitat": [
                "Macrocystis",
                "Bosques y matorrales",
                "Marismas y humedales",
                "Playas y dunas",
            ],
            "rank": [3, 4, 2, 1],
        }
    )

    d = d.join(habitat_rank, on="habitat", how="full")

    # f1 CALCULATION
    d = d.with_columns((pl.col("rank") * pl.col("health") * pl.col("km2")).alias("f1"))

    # STATUS
    scores_CP_status = (  # noqa: N806
        d.filter(
            pl.col("rank").is_not_null()
            & pl.col("health").is_not_null()
            & ~pl.col("health").is_nan()
            & pl.col("km2").is_not_null()
            & (pl.col("year") == scen_year)
        )
        .group_by("rgn_id")
        .agg(
            (
                pl.min_horizontal(
                    1.0, pl.col("f1").sum() / (pl.col("km2").sum() * pl.col("rank").max())
                )
                * 100
            ).alias("score")
        )
        .with_columns(pl.lit("status").alias("dimension"))
    )

    # TREND
    d_trend = d.filter(
        pl.col("rank").is_not_null() & pl.col("trend").is_not_null() & pl.col("km2").is_not_null()
    )

    if len(d_trend) > 0:
        trend_scores = (
            d_trend.group_by("rgn_id")
            .agg(
                (
                    (pl.col("rank") * pl.col("trend") * pl.col("km2")).sum()
                    / (pl.col("km2") * pl.col("rank")).sum()
                ).alias("score")
            )
            .with_columns(pl.lit("trend").alias("dimension"))
        )
        scores_CP = pl.concat([scores_CP_status, trend_scores])  # noqa: N806
    else:
        scores_CP = scores_CP_status  # noqa: N806

    scores_CP = scores_CP.rename({"rgn_id": "region_id"})  # noqa: N806
    scores_CP = scores_CP.select(["region_id", "dimension", "score"])  # noqa: N806

    status_df = scores_CP.filter(pl.col("dimension") == "status").clone()
    trend_df = scores_CP.filter(pl.col("dimension") == "trend").clone()

    return status_df, trend_df
