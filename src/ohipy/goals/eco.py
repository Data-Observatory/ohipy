"""ECO Goal - Economies

Calculates status and trend for the Economies goal based on GDP.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 847-949):
1. Load GDP data, set sector='gdp', rev_adj=gdp_usd
2. Status: Compare current revenue sum vs 5-year-ago value, capped at 1
3. Trend: Linear regression on revenue by sector, weighted mean
"""

from __future__ import annotations

from typing import cast

import polars as pl


def ECO(layers: dict[str, object]) -> tuple[pl.DataFrame, pl.DataFrame]:  # noqa: N802
    data_layers = cast(dict[str, object], layers["data"])

    def _get_layer(name: str) -> pl.DataFrame:
        layer = data_layers.get(name)
        if layer is None:
            raise ValueError(f"Missing layer: {name}")
        if isinstance(layer, pl.DataFrame):
            return layer.clone()
        return pl.DataFrame(layer)

    le_gdp = _get_layer("le_gdp")

    if "gdp_usd" not in le_gdp.columns:
        if len(le_gdp.columns) == 4:
            le_gdp = le_gdp.rename(
                {
                    le_gdp.columns[0]: "rgn_id",
                    le_gdp.columns[1]: "sector",
                    le_gdp.columns[2]: "year",
                    le_gdp.columns[3]: "gdp_usd",
                }
            )
        else:
            le_gdp = le_gdp.rename({"usd": "gdp_usd"})
    le_gdp = le_gdp.select(["rgn_id", "year", "sector", "gdp_usd"])

    eco = le_gdp.clone().with_columns(
        [
            pl.col("gdp_usd").alias("rev_adj"),
            pl.lit("gdp").alias("sector"),
        ]
    )
    eco = eco.select(["rgn_id", "year", "sector", "rev_adj"])

    # STATUS CALCULATION
    eco_status_pl = eco.filter(pl.col("rev_adj").is_not_null())
    max_year = eco_status_pl.select(pl.col("year").max()).item()
    eco_status_pl = eco_status_pl.filter(pl.col("year") >= max_year - 4)

    eco_status_pl = (
        eco_status_pl.group_by(["rgn_id", "year"])
        .agg(pl.col("rev_adj").sum().alias("rev_sum"))
        .sort(["rgn_id", "year"])
    )

    eco_status_pl = eco_status_pl.with_columns(
        pl.col("rev_sum").first().over("rgn_id").alias("rev_sum_first")
    )

    eco_status_pl = eco_status_pl.with_columns(
        ((pl.col("rev_sum") / pl.col("rev_sum_first")).clip(upper_bound=1) * 100).alias("score")
    )

    eco_status_out = (
        eco_status_pl.filter(pl.col("year") == max_year)
        .rename({"rgn_id": "region_id"})
        .with_columns(pl.lit("status").alias("dimension"))
        .select(["region_id", "score", "dimension"])
    )

    # TREND CALCULATION (Pure Polars - no pandas/scipy)
    eco_trend_pl = eco.filter(pl.col("rev_adj").is_not_null())
    max_year_trend = eco_trend_pl.select(pl.col("year").max()).item()
    eco_trend_pl = eco_trend_pl.filter(pl.col("year") >= max_year_trend - 4)

    eco_trend_pl = eco_trend_pl.sort(["rgn_id", "year", "sector"])
    eco_trend_pl = eco_trend_pl.with_columns(
        pl.col("rev_adj").sum().over(["rgn_id", "sector"]).alias("weight")
    )

    # slope = (n * sum(x*y) - sum(x) * sum(y)) / (n * sum(x^2) - sum(x)^2)
    # Then clip to [-1, 1] after multiplying by 5
    eco_trend_calc = eco_trend_pl.group_by(["rgn_id", "sector", "weight"]).agg(
        [
            (
                (
                    pl.len() * (pl.col("year") * pl.col("rev_adj")).sum()
                    - pl.col("year").sum() * pl.col("rev_adj").sum()
                )
                / (pl.len() * (pl.col("year") ** 2).sum() - pl.col("year").sum() ** 2)
                * 5
            )
            .clip(-1, 1)
            .alias("sector_trend")
        ]
    )

    eco_trend_final = (
        eco_trend_calc.with_columns(
            [
                pl.col("sector_trend").cast(pl.Float64),
                pl.col("weight").cast(pl.Float64),
            ]
        )
        .with_columns((pl.col("sector_trend") * pl.col("weight")).alias("_weighted"))
        .group_by("rgn_id")
        .agg(
            [
                pl.col("_weighted").sum().alias("_weighted_sum"),
                pl.col("weight").sum().alias("_weight_sum"),
            ]
        )
        .with_columns(
            pl.when(pl.col("_weight_sum") == 0)
            .then(None)
            .otherwise(pl.col("_weighted_sum") / pl.col("_weight_sum"))
            .alias("score")
        )
        .select(["rgn_id", "score"])
        .rename({"rgn_id": "region_id"})
        .with_columns(pl.lit("trend").alias("dimension"))
        .select(["region_id", "score", "dimension"])
    )

    # Filter out NaN scores
    econa_regions = (
        eco_status_out.filter(pl.col("score").is_null() | pl.col("score").is_nan())
        .select("region_id")
        .unique()
    )

    eco_status_out = eco_status_out.join(econa_regions, on="region_id", how="anti")
    eco_trend_final = eco_trend_final.join(econa_regions, on="region_id", how="anti")

    return eco_status_out, eco_trend_final
