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


def LIV(layers):
    """Calculate LIV (Livelihoods) goal status and trend using pure Polars."""

    def _get_layer(name: str) -> pl.DataFrame:
        layer = layers["data"].get(name)
        if layer is None:
            raise ValueError(f"Missing layer: {name}")
        if isinstance(layer, pl.DataFrame):
            return layer.clone()
        return pl.DataFrame(layer)

    # Load layers
    le_wages = (
        _get_layer("le_wage_sector")
        .rename({"wage": "wage_usd"})
        .select(["rgn_id", "year", "sector", "wage_usd"])
    )
    le_jobs = _get_layer("le_jobs_sector").select(["rgn_id", "year", "sector", "jobs"])
    le_workforce_size = (
        _get_layer("le_workforcesize_adj")
        .rename({"jobs": "jobs_all"})
        .select(["rgn_id", "year", "jobs_all"])
    )
    le_unemployment = (
        _get_layer("le_unemployment")
        .rename({"percent": "pct_unemployed"})
        .select(["rgn_id", "year", "pct_unemployed"])
    )

    # Define multipliers
    multipliers_jobs = pl.DataFrame(
        {
            "sector": ["Turismo", "Pesca", "Acuicultura", "Alojamiento", "Transporte"],
            "multiplier": [1.0, 1.582, 2.7, 1.0, 1.0],
        }
    ).with_columns(pl.col("multiplier").cast(pl.Float64))

    # Calculate employment
    le_employed = le_workforce_size.join(le_unemployment, on=["rgn_id", "year"], how="left")
    le_employed = le_employed.with_columns(
        ((100 - pl.col("pct_unemployed")) / 100).alias("proportion_employed")
    )
    le_employed = le_employed.with_columns(
        (pl.col("jobs_all") * pl.col("proportion_employed")).alias("employed")
    )

    # Build liv dataset
    liv = le_jobs.join(multipliers_jobs, on="sector", how="left")
    liv = liv.with_columns((pl.col("jobs") * pl.col("multiplier")).alias("jobs_mult"))
    liv = liv.join(le_employed, on=["rgn_id", "year"], how="left")
    liv = liv.with_columns((pl.col("jobs_mult") * pl.col("proportion_employed")).alias("jobs_adj"))
    liv = liv.join(le_wages, on=["rgn_id", "year", "sector"], how="left")
    liv = liv.sort(["year", "sector", "rgn_id"])

    # === STATUS CALCULATION ===
    liv_status1 = liv.filter(pl.col("jobs_adj").is_not_null() & pl.col("wage_usd").is_not_null())
    max_year = liv_status1.select(pl.col("year").max()).item()
    liv_status = liv_status1.filter(pl.col("year") >= max_year - 4)

    # Summarize across sectors
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

    # Get first year values for reference
    liv_status_pl = liv_status_pl.sort("rgn_id", "year")
    liv_status_pl = liv_status_pl.with_columns(
        [
            pl.col("jobs_sum").first().over("rgn_id").alias("jobs_sum_first"),
            pl.col("wages_avg").first().over("rgn_id").alias("wages_avg_first"),
        ]
    )

    # Calculate scores
    liv_status_pl = liv_status_pl.with_columns(
        [
            (pl.col("jobs_sum") / pl.col("jobs_sum_first")).clip(-1, 1).alias("x_jobs"),
            (pl.col("wages_avg") / pl.col("wages_avg_first")).clip(-1, 1).alias("x_wages"),
        ]
    )
    liv_status_pl = liv_status_pl.with_columns(
        ((pl.col("x_jobs") + pl.col("x_wages")) / 2 * 100).alias("score")
    )

    # Filter to most recent year
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

    # === TREND CALCULATION (Pure Polars - no pandas/scipy) ===
    liv_trend_data = liv.filter(pl.col("jobs_adj").is_not_null() & pl.col("wage_usd").is_not_null())
    max_year_trend = liv_trend_data.select(pl.col("year").max()).item()
    liv_trend_pl = liv_trend_data.filter(pl.col("year") >= max_year_trend - 4)
    liv_trend_pl = liv_trend_pl.sort(["rgn_id", "year", "sector"])

    # Calculate weight per sector (sum of jobs_adj per rgn_id-sector)
    liv_trend_pl = liv_trend_pl.with_columns(
        pl.col("jobs_adj").sum().over(["rgn_id", "sector"]).alias("weight")
    )

    # Melt value columns (matching R's reshape2::melt behavior)
    id_cols = ["rgn_id", "year", "sector", "weight"]
    value_cols = [c for c in liv_trend_pl.columns if c not in id_cols]
    liv_trend_melt = liv_trend_pl.melt(
        id_vars=id_cols, value_vars=value_cols, variable_name="metric", value_name="value"
    )

    # Calculate sector trend using pure polars expressions (slope formula)
    # slope = (n * sum(x*y) - sum(x) * sum(y)) / (n * sum(x^2) - sum(x)^2)
    # Then clip to [-1, 1] after multiplying by 5
    liv_trend_calc = liv_trend_melt.group_by(["metric", "rgn_id", "sector", "weight"]).agg(
        [
            (
                (
                    pl.len() * (pl.col("year") * pl.col("value")).sum()
                    - pl.col("year").sum() * pl.col("value").sum()
                )
                / (pl.len() * (pl.col("year") ** 2).sum() - pl.col("year").sum() ** 2)
                * 5
            )
            .clip(-1, 1)
            .alias("sector_trend")
        ]
    )

    # Weighted mean across sectors per region-metric
    liv_trend_by_metric = (
        liv_trend_calc.with_columns(
            [
                pl.col("sector_trend").cast(pl.Float64),
                pl.col("weight").cast(pl.Float64),
            ]
        )
        .with_columns((pl.col("sector_trend") * pl.col("weight")).alias("_weighted"))
        .group_by(["metric", "rgn_id"])
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
            .alias("metric_trend")
        )
        .select(["metric", "rgn_id", "metric_trend"])
    )

    # Mean across metrics per region
    liv_trend_out = (
        liv_trend_by_metric.group_by("rgn_id")
        .agg(pl.col("metric_trend").mean().alias("score"))
        .select(
            [
                pl.col("rgn_id").alias("region_id"),
                pl.col("score"),
            ]
        )
        .with_columns(pl.lit("trend").alias("dimension"))
        .select(["region_id", "score", "dimension"])
    )

    # Filter out NaN scores
    livna_regions = liv_status_out.filter(
        pl.col("score").is_null() | pl.col("score").is_nan()
    ).select("region_id")

    liv_status_out = liv_status_out.join(livna_regions, on="region_id", how="anti")
    liv_trend_out = liv_trend_out.join(livna_regions, on="region_id", how="anti")

    return liv_status_out, liv_trend_out
