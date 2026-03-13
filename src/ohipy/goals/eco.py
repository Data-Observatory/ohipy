"""ECO Goal - Economies

Calculates status and trend for the Economies goal based on GDP.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 847-949):
1. Load GDP data, set sector='gdp', rev_adj=gdp_usd
2. Status: Compare current revenue sum vs 5-year-ago value, capped at 1
3. Trend: Linear regression on revenue by sector, weighted mean
"""

import polars as pl
import pandas as pd
import numpy as np
from scipy import stats
import numpy as np
from scipy import stats


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

    # Convert to pandas for compatibility (layer may be polars or pandas)
    if hasattr(le_gdp_layer, "to_pandas"):
        le_gdp = le_gdp_layer.to_pandas().copy()
    else:
        le_gdp = le_gdp_layer.copy()
    if "gdp_usd" not in le_gdp.columns:
        if len(le_gdp.columns) == 4:
            le_gdp.columns = ["rgn_id", "sector", "year", "gdp_usd"]
        else:
            le_gdp = le_gdp.rename(columns={"usd": "gdp_usd"})
    le_gdp = le_gdp[["rgn_id", "year", "sector", "gdp_usd"]]

    # STEP 2: Create eco dataset
    eco = le_gdp.copy()
    eco["rev_adj"] = eco["gdp_usd"]
    eco["sector"] = "gdp"
    eco = eco[["rgn_id", "year", "sector", "rev_adj"]]

    # STEP 3: Calculate status
    eco_status = eco[~eco["rev_adj"].isna()].copy()
    max_year = eco_status["year"].max()
    eco_status = eco_status[eco_status["year"] >= max_year - 4].copy()

    # Sum revenue across sectors per region-year (using Polars)
    eco_status_pl = pl.DataFrame(eco_status)
    eco_status_pl = (
        eco_status_pl.group_by(["rgn_id", "year"])
        .agg(pl.col("rev_adj").sum().alias("rev_sum"))
        .sort("rgn_id", "year")
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
            (pl.col("rev_sum") / pl.col("rev_sum_first")).clip(upper_bound=1).alias("score"),
        ]
    )
    eco_status_pl = eco_status_pl.with_columns(
        [
            (pl.col("score") * 100).alias("score"),
        ]
    )

    # Filter to most recent year
    eco_status = eco_status_pl.filter(pl.col("year") == max_year).to_pandas()
    eco_status = eco_status.rename(columns={"rgn_id": "region_id"})
    eco_status["dimension"] = "status"
    eco_status = eco_status[["region_id", "score", "dimension"]]

    # STEP 4: Calculate trend
    eco_trend = eco[~eco["rev_adj"].isna()].copy()
    max_year_trend = eco_trend["year"].max()
    eco_trend = eco_trend[eco_trend["year"] >= max_year_trend - 4].copy()

    # Get sector weight using Polars window function
    eco_trend_pl = pl.DataFrame(eco_trend)
    eco_trend_pl = eco_trend_pl.sort("rgn_id", "year", "sector")
    eco_trend_pl = eco_trend_pl.with_columns(
        [
            pl.col("rev_adj").sum().over(["rgn_id", "sector"]).alias("weight"),
        ]
    )
    eco_trend = eco_trend_pl.to_pandas()

    # Calculate trend per region-sector (using scipy - keep pandas)
    def calc_sector_trend(group):
        if len(group) < 2:
            return pd.Series({"sector_trend": 0.0})

        years = group["year"].values
        values = group["rev_adj"].values

        slope, intercept, r_value, p_value, std_err = stats.linregress(years, values)
        sector_trend = slope * 5
        sector_trend = max(-1, min(1, sector_trend))

        return pd.Series({"sector_trend": sector_trend})

    eco_trend_calc = (
        eco_trend.groupby(["rgn_id", "sector", "weight"], group_keys=False)
        .apply(calc_sector_trend)
        .reset_index()
    )

    # Weighted mean across sectors per region (using Polars)
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
    )

    eco_trend_final = eco_trend_final_pl.to_pandas()
    eco_trend_final = eco_trend_final.rename(columns={"rgn_id": "region_id"})
    eco_trend_final["dimension"] = "trend"
    eco_trend_final = eco_trend_final[["region_id", "score", "dimension"]]

    # STEP 5: Filter out NaN scores (using Polars for efficiency)
    eco_status_pl = pl.DataFrame(eco_status)
    econa_regions = (
        eco_status_pl.filter(pl.col("score").is_null() | pl.col("score").is_nan())
        .select("region_id")
        .unique()
        .to_series()
        .to_list()
    )

    eco_status = eco_status_pl.filter(~pl.col("region_id").is_in(econa_regions)).to_pandas()
    eco_trend_final_pl = pl.DataFrame(eco_trend_final)
    eco_trend_final = eco_trend_final_pl.filter(
        ~pl.col("region_id").is_in(econa_regions)
    ).to_pandas()

    return eco_status, eco_trend_final
