"""OHI Dimension Calculations - Trend and Goal Index (Polars-native)."""

import polars as pl
import numpy as np
from scipy import stats


def calculate_trend(status_data, trend_years=None, default_trend=None):
    """Calculate trend from status values using linear regression.

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
    results = []

    for region_id in df["region_id"].unique().to_list():
        region_data = df.filter(pl.col("region_id") == region_id)

        if len(region_data) < 2:
            if default_trend is None:
                continue
            results.append({"region_id": region_id, "score": default_trend, "dimension": "trend"})
            continue

        adjust_trend_row = region_data.filter(pl.col("year") == adj_trend_year)
        if len(adjust_trend_row) == 0 or adjust_trend_row["status"].is_null().any():
            if default_trend is None:
                continue
            results.append({"region_id": region_id, "score": default_trend, "dimension": "trend"})
            continue

        adjust_trend = float(adjust_trend_row["status"][0])

        years = region_data["year"].to_numpy()
        statuses = region_data["status"].to_numpy()

        result = stats.linregress(years, statuses)
        slope_value = float(result.slope)

        if slope_value == 0:
            score = 0.0
        elif adjust_trend == 0:
            score = 1.0 if slope_value > 0 else -1.0
        else:
            score = (slope_value / adjust_trend) * 5

        score = max(-1.0, min(1.0, score))
        score = round(score, 4)

        results.append({"region_id": region_id, "score": score, "dimension": "trend"})

    return pl.DataFrame(results)


def calculate_goal_index(
    id, status, trend, resilience, pressure, DISCOUNT=1.0, BETA=0.67, default_trend=0
):
    """Calculate goal index from components.

    Formula:
    - xF (future) = ((1 + BETA*trend + (1-BETA)*r_p) * status) / 2
    - score = (status + future) / 2
    """
    # Check for None/NaN status first - return early with NaN results
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
