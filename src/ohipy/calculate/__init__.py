"""OHI Dimension Calculations - Trend and Goal Index (Polars-native)."""

import polars as pl
import numpy as np


def calculate_trend(status_data, trend_years=None, default_trend=None):
    """Calculate trend from status values using vectorized linear regression.

    Args:
        status_data: polars DataFrame with columns: rgn_id/region_id, year, status
        trend_years: List of years to include
        default_trend: Default value when trend cannot be calculated

    Returns:
        pl.DataFrame: [region_id, score, dimension]
    """
    df = status_data.clone()

    if "rgn_id" in df.columns:
        df = df.rename({"rgn_id": "region_id"})
    if "scenario_year" in df.columns:
        df = df.rename({"scenario_year": "year"})

    df = df.select(["region_id", "year", "status"])

    if trend_years is not None:
        df = df.filter(pl.col("year").is_in(trend_years))

    df = df.filter(pl.col("status").is_not_null())
    df = df.unique(subset=["region_id", "year"])

    if trend_years is None:
        trend_years = sorted(df["year"].unique().to_list())

    if len(trend_years) == 0:
        return pl.DataFrame(
            schema={"region_id": pl.Int64, "score": pl.Float64, "dimension": pl.Utf8}
        )

    adj_trend_year = min(trend_years)

    # Vectorized linear regression using closed-form OLS
    # slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x^2)
    agg = df.group_by("region_id").agg(
        [
            pl.len().alias("n"),
            pl.col("year").sum().alias("sum_x"),
            pl.col("status").sum().alias("sum_y"),
            (pl.col("year") ** 2).sum().alias("sum_xx"),
            (pl.col("year") * pl.col("status")).sum().alias("sum_xy"),
            pl.col("status").filter(pl.col("year") == adj_trend_year).first().alias("adjust_trend"),
        ]
    )

    # Calculate slope
    agg = agg.with_columns(
        [
            (pl.col("n") * pl.col("sum_xy") - pl.col("sum_x") * pl.col("sum_y")).alias("numerator"),
            (pl.col("n") * pl.col("sum_xx") - pl.col("sum_x") ** 2).alias("denominator"),
        ]
    )

    # Handle edge cases
    agg = agg.with_columns(
        [
            pl.when(pl.col("denominator") == 0)
            .then(0.0)
            .otherwise(pl.col("numerator") / pl.col("denominator"))
            .alias("slope"),
        ]
    )

    # Calculate score
    agg = agg.with_columns(
        [
            pl.when(pl.col("n") < 2)
            .then(pl.lit(default_trend).cast(pl.Float64))
            .when(pl.col("adjust_trend").is_null())
            .then(pl.lit(default_trend).cast(pl.Float64))
            .when(pl.col("slope") == 0)
            .then(0.0)
            .when(pl.col("adjust_trend") == 0)
            .then(pl.when(pl.col("slope") > 0).then(1.0).otherwise(-1.0))
            .otherwise((pl.col("slope") / pl.col("adjust_trend")) * 5)
            .alias("score"),
        ]
    )

    # Clip and round
    agg = agg.with_columns(
        [
            pl.col("score").clip(-1.0, 1.0).round(4).alias("score"),
        ]
    )

    # Filter out None scores when no default
    if default_trend is None:
        agg = agg.filter(pl.col("score").is_not_null())
    else:
        agg = agg.filter(pl.col("n") >= 2)

    result = agg.select(
        [
            pl.col("region_id"),
            pl.col("score"),
            pl.lit("trend").alias("dimension"),
        ]
    )

    return result


def calculate_goal_index(
    id, status, trend, resilience, pressure, DISCOUNT=1.0, BETA=0.67, default_trend=0
):
    """Calculate goal index from components.

    Formula:
    - xF (future) = ((1 + BETA*trend + (1-BETA)*r_p) * status) / 2
    - score = (status + future) / 2
    """
    if status is None or (isinstance(status, float) and np.isnan(status)):
        return {
            "id": id,
            "x": status,
            "t": trend if trend is not None else default_trend,
            "r": 0.0,
            "p": 0.0,
            "xF": np.nan,
            "score": np.nan,
        }

    if trend is None or (isinstance(trend, float) and np.isnan(trend)):
        trend = default_trend

    resilience = (
        0.0
        if resilience is None or (isinstance(resilience, float) and np.isnan(resilience))
        else resilience
    )
    pressure = (
        0.0
        if pressure is None or (isinstance(pressure, float) and np.isnan(pressure))
        else pressure
    )

    resilience = min(resilience, pressure)
    r_p = resilience - pressure

    xF = (1 + BETA * trend + (1 - BETA) * r_p) * status
    xF = max(0.0, min(1.0, xF))

    score = (status + xF) / 2
    score = max(0.0, min(1.0, score))

    return {
        "id": id,
        "x": status,
        "t": trend,
        "r": resilience,
        "p": pressure,
        "xF": xF,
        "score": score,
    }


__all__ = ["calculate_trend", "calculate_goal_index"]
