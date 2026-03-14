"""LIV Goal - Livelihoods

Calculates status and trend for the Livelihoods goal based on jobs and wages.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 704-845):
1. Load wages, jobs, workforce size, unemployment data
2. Apply job multipliers by sector
3. Adjust jobs by employment proportion
4. Status: Compare current vs 5-year-ago values for jobs (sum) and wages (avg)
5. Trend: Linear regression on jobs and wages by sector, weighted average
"""

import polars as pl
from scipy import stats
from typing import Any, cast


def LIV(layers):
    """
    Calculate LIV (Livelihoods) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """

    def _layer_as_polars(name: str) -> pl.DataFrame:
        layer = layers["data"].get(name)
        if layer is None:
            raise ValueError(f"Missing layer: {name}")
        if isinstance(layer, pl.DataFrame):
            return layer.clone()
        return pl.DataFrame(layer)

    # STEP 1: Load layers
    le_wages_layer = _layer_as_polars("le_wage_sector")
    if le_wages_layer is None:
        raise ValueError("Missing layer: le_wage_sector")
    le_wages = le_wages_layer.clone()
    le_wages = le_wages.rename({"wage": "wage_usd"})
    le_wages = le_wages.select(["rgn_id", "year", "sector", "wage_usd"])

    le_jobs_layer = _layer_as_polars("le_jobs_sector")
    if le_jobs_layer is None:
        raise ValueError("Missing layer: le_jobs_sector")
    le_jobs = le_jobs_layer.clone()
    le_jobs = le_jobs.select(["rgn_id", "year", "sector", "jobs"])

    le_workforce_layer = _layer_as_polars("le_workforcesize_adj")
    if le_workforce_layer is None:
        raise ValueError("Missing layer: le_workforcesize_adj")
    le_workforce_size = le_workforce_layer.clone()
    le_workforce_size = le_workforce_size.rename({"jobs": "jobs_all"})
    le_workforce_size = le_workforce_size.select(["rgn_id", "year", "jobs_all"])

    le_unemployment_layer = _layer_as_polars("le_unemployment")
    if le_unemployment_layer is None:
        raise ValueError("Missing layer: le_unemployment")
    le_unemployment = le_unemployment_layer.clone()
    le_unemployment = le_unemployment.rename({"percent": "pct_unemployed"})
    le_unemployment = le_unemployment.select(["rgn_id", "year", "pct_unemployed"])

    # STEP 2: Define multipliers
    multipliers_jobs = pl.DataFrame(
        {
            "sector": ["Turismo", "Pesca", "Acuicultura", "Alojamiento", "Transporte"],
            "multiplier": [1.0, 1.582, 2.7, 1.0, 1.0],
        }
    ).with_columns(pl.col("multiplier").cast(pl.Float64))

    # STEP 3: Calculate employment
    le_employed = le_workforce_size.join(le_unemployment, on=["rgn_id", "year"], how="left")
    le_employed = le_employed.with_columns(
        [
            ((100 - pl.col("pct_unemployed")) / 100).alias("proportion_employed"),
            (pl.col("jobs_all") * ((100 - pl.col("pct_unemployed")) / 100)).alias("employed"),
        ]
    )

    # Convert rgn_id to string, pad, then back to int (mimicking R code)
    le_employed = le_employed.with_columns(
        pl.col("rgn_id").cast(pl.Utf8).str.zfill(5).cast(pl.Int64).alias("rgn_id")
    )

    # STEP 4: Build liv dataset
    liv = le_jobs.join(multipliers_jobs, on="sector", how="left")
    liv = liv.with_columns((pl.col("jobs") * pl.col("multiplier")).alias("jobs_mult"))
    liv = liv.join(le_employed, on=["rgn_id", "year"], how="left")
    liv = liv.with_columns((pl.col("jobs_mult") * pl.col("proportion_employed")).alias("jobs_adj"))
    liv = liv.join(le_wages, on=["rgn_id", "year", "sector"], how="left")
    liv = liv.sort(["year", "sector", "rgn_id"])

    # STEP 5: Calculate status
    liv_status1 = liv.filter(pl.col("jobs_adj").is_not_null() & pl.col("wage_usd").is_not_null())

    max_year = liv_status1.select(pl.col("year").max()).item()
    liv_status = liv_status1.filter(pl.col("year") >= max_year - 4)

    # Summarize across sectors using Polars
    liv_status_pl = (
        liv_status.sort(["rgn_id", "year", "sector"])
        .group_by(["rgn_id", "year"])
        .agg(
            [
                pl.col("jobs_adj").sum().alias("jobs_sum"),
                pl.col("wage_usd").mean().alias("wages_avg"),
            ]
        )
    )

    # For each region, get first year values using window function
    liv_status_pl = liv_status_pl.sort("rgn_id", "year")
    liv_status_pl = liv_status_pl.with_columns(
        [
            pl.col("jobs_sum").first().over("rgn_id").alias("jobs_sum_first"),
            pl.col("wages_avg").first().over("rgn_id").alias("wages_avg_first"),
        ]
    )

    # Calculate scores using Polars expressions
    liv_status_pl = liv_status_pl.with_columns(
        [
            (pl.col("jobs_sum") / pl.col("jobs_sum_first")).clip(-1, 1).alias("x_jobs"),
            (pl.col("wages_avg") / pl.col("wages_avg_first")).clip(-1, 1).alias("x_wages"),
        ]
    )
    liv_status_pl = liv_status_pl.with_columns(
        [((pl.col("x_jobs") + pl.col("x_wages")) / 2 * 100).alias("score")]
    )

    # Filter to most recent year and convert back to pandas
    liv_status_out = (
        liv_status_pl.filter(pl.col("year") == max_year)
        .select(
            [
                pl.col("rgn_id").alias("region_id"),
                pl.col("score"),
            ]
        )
        .with_columns(pl.lit("status").alias("dimension"))
        .select(["region_id", "score", "dimension"])
    )

    # STEP 6: Calculate trend
    liv_trend_data = liv.filter(pl.col("jobs_adj").is_not_null() & pl.col("wage_usd").is_not_null())
    max_year_trend = liv_trend_data.select(pl.col("year").max()).item()
    liv_trend_data = liv_trend_data.filter(pl.col("year") >= max_year_trend - 4)

    # Get sector weight using Polars
    liv_trend_pl = liv_trend_data.sort(["rgn_id", "year", "sector"])
    liv_trend_pl = liv_trend_pl.with_columns(
        [pl.col("jobs_adj").sum().over(["rgn_id", "sector"]).alias("weight")]
    )

    # Melt ALL value columns into single metric (mimicking R's melt behavior)
    # R melts all columns except the id columns
    id_cols = ["rgn_id", "year", "sector", "weight"]
    value_cols = [c for c in liv_trend_pl.columns if c not in id_cols]

    liv_trend_melt_pl = liv_trend_pl.melt(
        id_vars=id_cols, value_vars=value_cols, variable_name="metric", value_name="value"
    )

    import pandas as pd

    liv_trend_melt = pd.DataFrame(liv_trend_melt_pl.to_dicts())

    # Calculate trend per metric-region-sector
    def calc_sector_trend(group):
        if len(group) < 2:
            return pd.Series({"sector_trend": 0.0})

        years = group["year"].values
        values = group["value"].values

        regression = stats.linregress(years, values)
        sector_trend = float(cast(Any, regression)[0]) * 5
        sector_trend = max(-1, min(1, sector_trend))

        return pd.Series({"sector_trend": sector_trend})

    liv_trend_calc = (
        liv_trend_melt.groupby(["metric", "rgn_id", "sector", "weight"], group_keys=False)
        .apply(calc_sector_trend)
        .reset_index()
    )

    # Weighted mean across sectors per region-metric using Polars
    liv_trend_calc_pl = pl.DataFrame(liv_trend_calc.to_dict("records"))
    liv_trend_by_metric_pl = (
        liv_trend_calc_pl.with_columns(
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
        .group_by(["metric", "rgn_id"])
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
                .alias("metric_trend"),
            ]
        )
        .select(["metric", "rgn_id", "metric_trend"])
    )

    # Mean across metrics per region using Polars
    liv_trend_pl = (
        liv_trend_by_metric_pl.group_by("rgn_id")
        .agg(
            [
                pl.col("metric_trend").mean().alias("score"),
            ]
        )
        .select(
            [
                pl.col("rgn_id").alias("region_id"),
                pl.col("score"),
            ]
        )
    )

    liv_trend_out = liv_trend_pl.with_columns(pl.lit("trend").alias("dimension")).select(
        ["region_id", "score", "dimension"]
    )

    # STEP 7: Filter out NaN scores
    livna_regions = liv_status_out.filter(
        pl.col("score").is_null() | pl.col("score").is_nan()
    ).select("region_id")

    liv_status_out = liv_status_out.join(livna_regions, on="region_id", how="anti")
    liv_trend_out = liv_trend_out.join(livna_regions, on="region_id", how="anti")

    liv_status_df = pd.DataFrame(liv_status_out.to_dicts())
    liv_trend_df = pd.DataFrame(liv_trend_out.to_dicts())

    return liv_status_df, liv_trend_df
