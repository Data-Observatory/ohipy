"""ECO Goal - Economies

Calculates status and trend for the Economies goal based on GDP.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 847-949):
1. Load GDP data, set sector='gdp', rev_adj=gdp_usd
2. Status: Compare current revenue sum vs 5-year-ago value, capped at 1
3. Trend: Linear regression on revenue by sector, weighted mean
"""

import polars as pl
from scipy import stats
from typing import cast


def ECO(layers):
    """
    Calculate ECO (Economies) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    # STEP 1: Load GDP layer
    le_gdp_layer = layers["data"].get("le_gdp")
    if le_gdp_layer is None:
        raise ValueError("Missing layer: le_gdp")

    if isinstance(le_gdp_layer, pl.DataFrame):
        le_gdp = le_gdp_layer.clone()
    else:
        le_gdp = pl.from_pandas(le_gdp_layer.copy())

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

    # STEP 2: Create eco dataset
    eco = le_gdp.clone().with_columns(
        [
            pl.col("gdp_usd").alias("rev_adj"),
            pl.lit("gdp").alias("sector"),
        ]
    )
    eco = eco.select(["rgn_id", "year", "sector", "rev_adj"])

    # STEP 3: Calculate status
    eco_status_pl = eco.filter(pl.col("rev_adj").is_not_null())
    max_year = eco_status_pl.select(pl.col("year").max()).item()
    eco_status_pl = eco_status_pl.filter(pl.col("year") >= max_year - 4)

    eco_status_pl = (
        eco_status_pl.group_by(["rgn_id", "year"])
        .agg(pl.col("rev_adj").sum().alias("rev_sum"))
        .sort(["rgn_id", "year"])
    )

    # Get first year value per region using Polars window function
    eco_status_pl = eco_status_pl.with_columns(
        [
            pl.col("rev_sum").first().over("rgn_id").alias("rev_sum_first"),
        ]
    )

    # Calculate score (capped at 1)
    eco_status_pl = eco_status_pl.with_columns(
        [
            ((pl.col("rev_sum") / pl.col("rev_sum_first")).clip(upper_bound=1) * 100).alias(
                "score"
            ),
        ]
    )

    # Filter to most recent year
    eco_status_pl = (
        eco_status_pl.filter(pl.col("year") == max_year)
        .rename({"rgn_id": "region_id"})
        .with_columns(pl.lit("status").alias("dimension"))
        .select(["region_id", "score", "dimension"])
    )

    # STEP 4: Calculate trend
    eco_trend_pl = eco.filter(pl.col("rev_adj").is_not_null())
    max_year_trend = eco_trend_pl.select(pl.col("year").max()).item()
    eco_trend_pl = eco_trend_pl.filter(pl.col("year") >= max_year_trend - 4)

    # Get sector weight using Polars window function
    eco_trend_pl = eco_trend_pl.sort(["rgn_id", "year", "sector"])
    eco_trend_pl = eco_trend_pl.with_columns(
        [
            pl.col("rev_adj").sum().over(["rgn_id", "sector"]).alias("weight"),
        ]
    )

    eco_trend = eco_trend_pl.to_pandas()

    # Calculate trend per region-sector (using scipy - keep pandas)
    def calc_sector_trend(group):
        if len(group) < 2:
            return 0.0

        years = group["year"].to_numpy()
        values = group["rev_adj"].to_numpy()

        regression = cast(tuple[float, float, float, float, float], stats.linregress(years, values))
        sector_trend = regression[0] * 5.0
        sector_trend = max(-1.0, min(1.0, sector_trend))

        return float(sector_trend)

    eco_trend_calc = eco_trend.groupby(["rgn_id", "sector", "weight"], group_keys=False).apply(
        calc_sector_trend
    )
    eco_trend_calc = eco_trend_calc.to_frame(name="sector_trend").reset_index()

    eco_trend_calc_pl = pl.DataFrame(eco_trend_calc)

    eco_trend_final_pl = (
        eco_trend_calc_pl.with_columns(
            [
                pl.col("sector_trend").cast(pl.Float64).alias("sector_trend"),
                pl.col("weight").cast(pl.Float64).alias("weight"),
            ]
        )
        .with_columns(
            [
                (pl.col("sector_trend") * pl.col("weight")).alias("_weighted"),
            ]
        )
        .group_by("rgn_id")
        .agg(
            [
                pl.col("_weighted").sum().alias("_weighted_sum"),
                pl.col("weight").sum().alias("_weight_sum"),
            ]
        )
        .with_columns(
            [
                pl.when(pl.col("_weight_sum") == 0)
                .then(None)
                .otherwise(pl.col("_weighted_sum") / pl.col("_weight_sum"))
                .alias("score"),
            ]
        )
        .select(["rgn_id", "score"])
        .rename({"rgn_id": "region_id"})
        .with_columns(pl.lit("trend").alias("dimension"))
        .select(["region_id", "score", "dimension"])
    )

    # STEP 5: Filter out NaN scores (using Polars for efficiency)
    econa_regions = (
        eco_status_pl.filter(pl.col("score").is_null() | pl.col("score").is_nan())
        .select("region_id")
        .unique()
        .to_series()
        .to_list()
    )

    eco_status = eco_status_pl.filter(~pl.col("region_id").is_in(econa_regions)).to_pandas()
    eco_trend_final = eco_trend_final_pl.filter(
        ~pl.col("region_id").is_in(econa_regions)
    ).to_pandas()

    return eco_status, eco_trend_final
