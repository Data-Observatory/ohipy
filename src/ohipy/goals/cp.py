"""CP Goal - Coastal Protection

Calculates status and trend for the Coastal Protection goal based on habitat extent.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 534-616):
1. Load habitat extension data for last 5 years
2. Calculate trend per region-habitat: coef(year) * sd(year) / sd(km2) * 5, clamp to [-1,1]
3. Calculate health per region-habitat: km2 / max(km2)
4. Define habitat ranks: Macrocystis=3, Bosques y matorrales=4, Marismas y humedales=2, Playas y dunas=1
5. Calculate f1 = rank * health * km2
6. Status: sum(f1) / (sum(km2) * max(rank)) * 100, capped at 100
7. Trend: sum(rank * trend * km2) / sum(km2 * rank)
"""

from typing import cast

import numpy as np
import pandas as pd
from scipy import stats


def _ensure_pandas(df):
    """Convert polars DataFrame to pandas if needed, pass through pandas unchanged."""
    if df is None:
        return None
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    return df


def CP(layers):
    """
    Calculate CP (Coastal Protection) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    # Get scenario year
    scen_year = layers["data"].get("scenario_year", 2024)

    # STEP 1: Load habitat extension data
    extent_layer = _ensure_pandas(layers["data"].get("cp_habitat_extension"))
    if extent_layer is None:
        raise ValueError("Missing layer: cp_habitat_extension")

    extent = extent_layer.copy()
    # Columns: rgn_id, habitat, year, value
    extent = extent.rename(columns={"value": "km2"})

    # Filter to last 5 years
    extent = extent[extent["year"] >= (scen_year - 4)]
    extent = extent[["year", "rgn_id", "habitat", "km2"]]

    # STEP 2: Calculate trend per region-habitat
    def calculate_habitat_trend(group):
        if len(group) < 2:
            return pd.Series({"trend": np.nan})

        years = group["year"].values
        km2_vals = group["km2"].values

        # Check for zero variance
        if np.std(km2_vals) == 0:
            return pd.Series({"trend": np.nan})

        # Linear regression
        result = cast(tuple[float, float, float, float, float], stats.linregress(years, km2_vals))
        slope_val = result[0]

        # Calculate trend: slope * sd(year) / sd(km2) * 5
        trend_val = slope_val * np.std(years) / np.std(km2_vals) * 5

        # Clamp to [-1, 1]
        trend_val = max(-1.0, min(1.0, trend_val))

        return pd.Series({"trend": trend_val})

    trend = (
        extent.groupby(["rgn_id", "habitat"], group_keys=True)
        .apply(calculate_habitat_trend)
        .reset_index()
    )

    # STEP 3: Calculate health per region-habitat
    health = (
        extent.groupby(["rgn_id", "habitat"])
        .apply(lambda x: x.assign(km2_max=x["km2"].max(), health=x["km2"] / x["km2"].max()))
        .reset_index()
    )

    # STEP 4: Merge extent, health, trend
    d = extent.merge(
        health[["year", "rgn_id", "habitat", "health"]],
        on=["year", "rgn_id", "habitat"],
        how="left",
    )
    d = d.merge(trend, on=["rgn_id", "habitat"], how="left")

    # STEP 5: Define habitat ranks
    habitat_rank = pd.DataFrame(
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

    d = d.merge(habitat_rank, on="habitat", how="outer")

    # STEP 6: Calculate f1
    d["f1"] = d["rank"] * d["health"] * d["km2"]

    # STEP 7: Calculate status (year == 2024)
    scores_CP = d[
        (~d["rank"].isna()) & (~d["health"].isna()) & (~d["km2"].isna()) & (d["year"] == 2024)
    ].copy()

    scores_CP = (
        scores_CP.groupby("rgn_id")
        .apply(
            lambda x: pd.Series(
                {"score": min(1.0, x["f1"].sum() / (x["km2"].sum() * x["rank"].max())) * 100}
            )
        )
        .reset_index()
    )
    scores_CP["dimension"] = "status"

    # STEP 8: Calculate trend
    d_trend = d[(~d["rank"].isna()) & (~d["trend"].isna()) & (~d["km2"].isna())].copy()

    if len(d_trend) > 0:
        trend_scores = (
            d_trend.groupby("rgn_id")
            .apply(
                lambda x: pd.Series(
                    {
                        "score": (x["rank"] * x["trend"] * x["km2"]).sum()
                        / (x["km2"] * x["rank"]).sum()
                    }
                )
            )
            .reset_index()
        )
        trend_scores["dimension"] = "trend"

        scores_CP = pd.concat([scores_CP, trend_scores], ignore_index=True)

    # Finalize
    scores_CP = scores_CP.rename(columns={"rgn_id": "region_id"})
    scores_CP = scores_CP[["region_id", "dimension", "score"]]

    # Split into status and trend
    status_df = scores_CP[scores_CP["dimension"] == "status"].copy()
    trend_df = scores_CP[scores_CP["dimension"] == "trend"].copy()

    return status_df, trend_df
