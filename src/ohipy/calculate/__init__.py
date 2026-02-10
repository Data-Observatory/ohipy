"""OHI Dimension Calculations - Trend and Goal Index."""

import pandas as pd
import numpy as np
from scipy import stats
from typing import cast


def calculate_trend(status_data, trend_years=None, default_trend=None):
    """
    Calculate trend dimension from status values over time using linear regression.

    Trend is calculated as the proportional change in status across time. Typically
    five year periods are used (scenario_year-4 to scenario_year).

    Algorithm (from ohicore/R/CalculateTrend.R):
    1. Filter status data to trend_years
    2. For each region, fit linear model: status ~ year
    3. Calculate trend = (slope / adjust_trend) * 5
       where adjust_trend = status at min(trend_years)
    4. Clamp to [-1, 1] and round to 4 decimals

    Args:
        status_data: DataFrame with columns: rgn_id (or region_id), year, status
        trend_years: List of years to include (e.g., [2020, 2021, 2022, 2023, 2024])
                    If None, uses all years in data
        default_trend: Default value when trend cannot be calculated. If None,
            rows with insufficient data are skipped.

    Returns:
        pd.DataFrame: DataFrame with columns [region_id, score, dimension]
    """
    # Standardize column names
    df = status_data.copy()
    if "rgn_id" in df.columns:
        df = df.rename(columns={"rgn_id": "region_id"})
    if "scenario_year" in df.columns:
        df = df.rename(columns={"scenario_year": "year"})

    # Select required columns
    df = df[["region_id", "year", "status"]].copy()

    # Filter to trend years if specified
    if trend_years is not None:
        df = df[df["year"].isin(trend_years)]

    # Remove NA status values
    df = df.dropna(subset=["status"])

    # Remove duplicates
    df = df.drop_duplicates()

    # If no trend years specified, determine from data
    if trend_years is None:
        trend_years = sorted(df["year"].unique())

    if len(trend_years) == 0:
        return pd.DataFrame(columns=pd.Index(["region_id", "score", "dimension"]))

    adj_trend_year = min(trend_years)

    # Calculate trend for each region
    results = []

    for region_id in df["region_id"].unique():
        region_data = df[df["region_id"] == region_id].copy()

        # Need at least 2 points for linear regression
        if len(region_data) < 2:
            # Use default trend if insufficient data (R leaves it NA)
            if default_trend is None:
                continue
            results.append(
                {
                    "region_id": region_id,
                    "score": default_trend,
                    "dimension": "trend",
                }
            )
            continue

        # Get status at adjustment year (for normalization)
        adjust_trend_row = region_data[region_data["year"] == adj_trend_year]
        if len(adjust_trend_row) == 0 or adjust_trend_row["status"].isna().all():
            # No status at min year, use default (R leaves it NA)
            if default_trend is None:
                continue
            results.append(
                {
                    "region_id": region_id,
                    "score": default_trend,
                    "dimension": "trend",
                }
            )
            continue

        adjust_trend = float(adjust_trend_row["status"].iloc[0])

        # Fit linear model: status ~ year
        years = region_data["year"].values
        statuses = region_data["status"].values

        # Linear regression
        result = stats.linregress(years, statuses)
        slope_value = cast(float, result[0])

        # Calculate trend score
        if slope_value == 0:
            score = 0.0
        elif adjust_trend == 0:
            # When adjust_trend is 0, R would calculate slope/0 which gives Inf/-Inf
            # This then gets clamped to 1/-1. We replicate this behavior.
            score = 1.0 if slope_value > 0 else -1.0
        else:
            score = (slope_value / float(adjust_trend)) * 5

        # Clamp to [-1, 1]
        score = max(-1.0, min(1.0, score))

        # Round to 4 decimals
        score = round(score, 4)

        results.append({"region_id": region_id, "score": score, "dimension": "trend"})

    # Convert to DataFrame
    result_df = pd.DataFrame(results)

    return result_df


def calculate_goal_index(
    id, status, trend, resilience, pressure, DISCOUNT=1.0, BETA=0.67, default_trend=0
):
    """
    Calculate goal index (likely future state and score) from components.

    Formula (from ohicore/R/CalculateGoalIndex.R):
    - xF (future) = ((1 + BETA*trend + (1-BETA)*r_p) * status) / 2
      where r_p = resilience - pressure
    - score = (status + future) / 2

    Args:
        id: Region ID
        status: Current status (0-1 scale)
        trend: Trend (-1 to 1)
        resilience: Resilience (0-1 scale)
        pressure: Pressure (0-1 scale)
        DISCOUNT: Discount factor for future state (default: 1.0)
        BETA: Relative weight of trend vs resilience/pressure (default: 0.67)
        default_trend: Default trend if NA (default: 0)

    Returns:
        dict: Dictionary with keys: id, x (status), t (trend), r (resilience),
              p (pressure), xF (future), score
    """
    # Handle NA values
    if pd.isna(trend):
        trend = default_trend

    # R converts NaN to 0 before calculation (CalculateGoalIndex.R lines 72-80)
    # This ensures NaN pressures/resilience "drop out" of the equation
    resilience = 0.0 if pd.isna(resilience) else resilience
    pressure = 0.0 if pd.isna(pressure) else pressure

    # Cap resilience to not exceed pressure
    resilience = min(resilience, pressure)

    # Calculate resilience-pressure differential
    r_p = resilience - pressure

    # Calculate likely future state
    # xF = (1 + BETA*trend + (1-BETA)*r_p) * status
    xF = (1 + BETA * trend + (1 - BETA) * r_p) * status

    # Clamp future to [0, 1]
    xF = max(0.0, min(1.0, xF))

    # NEW: If status is NaN, xF and score should also be NaN (not calculated)
    # This matches R behavior where NA status leads to NA future and score
    if pd.isna(status):
        xF = np.nan
        score = np.nan
    else:
        # Calculate score as average of status and future
        score = (status + xF) / 2

        # Clamp score to [0, 1]
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


# Module exports
__all__ = ["calculate_trend", "calculate_goal_index"]
