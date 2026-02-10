"""ECO Goal - Economies

Calculates status and trend for the Economies goal based on GDP.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 847-949):
1. Load GDP data, set sector='gdp', rev_adj=gdp_usd
2. Status: Compare current revenue sum vs 5-year-ago value, capped at 1
3. Trend: Linear regression on revenue by sector, weighted mean
"""

import pandas as pd
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

    # Sum revenue across sectors per region-year
    eco_status = (
        eco_status.groupby(["rgn_id", "year"]).agg({"rev_adj": "sum"}).reset_index()
    )
    eco_status = eco_status.rename(columns={"rev_adj": "rev_sum"})

    # Get first year value per region
    eco_status = eco_status.sort_values(["rgn_id", "year"])
    eco_status["rev_sum_first"] = eco_status.groupby("rgn_id")["rev_sum"].transform(
        "first"
    )

    # Calculate score (capped at 1)
    eco_status["score"] = (eco_status["rev_sum"] / eco_status["rev_sum_first"]).clip(
        upper=1
    ) * 100

    # Filter to most recent year
    eco_status = eco_status[eco_status["year"] == max_year].copy()
    eco_status = eco_status.rename(columns={"rgn_id": "region_id"})
    eco_status["dimension"] = "status"
    eco_status = eco_status[["region_id", "score", "dimension"]]

    # STEP 4: Calculate trend
    eco_trend = eco[~eco["rev_adj"].isna()].copy()
    max_year_trend = eco_trend["year"].max()
    eco_trend = eco_trend[eco_trend["year"] >= max_year_trend - 4].copy()

    # Get sector weight
    eco_trend = eco_trend.sort_values(["rgn_id", "year", "sector"])
    eco_trend["weight"] = eco_trend.groupby(["rgn_id", "sector"])["rev_adj"].transform(
        "sum"
    )

    # Calculate trend per region-sector
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

    # Weighted mean across sectors per region
    eco_trend_final = (
        eco_trend_calc.groupby("rgn_id")
        .apply(
            lambda x: pd.Series(
                {"score": np.average(x["sector_trend"], weights=x["weight"])}
            )
        )
        .reset_index()
    )

    eco_trend_final = eco_trend_final.rename(columns={"rgn_id": "region_id"})
    eco_trend_final["dimension"] = "trend"
    eco_trend_final = eco_trend_final[["region_id", "score", "dimension"]]

    # STEP 5: Filter out NaN scores
    econa = eco_status[
        eco_status["score"].isna()
        | (
            eco_status["score"].apply(
                lambda x: np.isnan(x) if isinstance(x, float) else False
            )
        )
    ]
    econa_regions = econa["region_id"].unique()

    eco_status = eco_status[~eco_status["region_id"].isin(econa_regions)]
    eco_trend_final = eco_trend_final[~eco_trend_final["region_id"].isin(econa_regions)]

    return eco_status, eco_trend_final
