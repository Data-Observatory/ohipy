"""HAB Goal - Habitats

Calculates status and trend for the Habitats goal.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 1198-1272):
1. Load hab_extension and hab_area
2. Merge and calculate reference: ref = max(value/area_km2) per region-habitat
3. Filter out habitats with all zeros in 2018-2022
4. Count number of habitats per region
5. Calculate C = (value/area_km2) / ref, sum per region-year
6. Status = (sum(C) / n_habitats) * 100
7. Trend: Calculate using calculate_trend()
"""

import pandas as pd
import numpy as np
from ..calculate import calculate_trend


def _ensure_pandas(df):
    """Convert polars DataFrame to pandas if needed, pass through pandas unchanged."""
    if df is None:
        return None
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    return df


def HAB(layers):
    """
    Calculate HAB (Habitats) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    scenario_year = layers["data"]["scenario_year"]

    # STEP 1: Load hab_extension layer
    hab_extension_layer = _ensure_pandas(layers["data"].get("hab_extension"))
    if hab_extension_layer is None:
        raise ValueError("Missing layer: hab_extension")

    hab = hab_extension_layer.copy()
    hab = hab.rename(columns={"rgn_id": "rgn_id", "value": "value"})
    hab = hab[["rgn_id", "year", "habitat", "value"]]

    # STEP 2: Load hab_area layer
    hab_area_layer = _ensure_pandas(layers["data"].get("hab_area"))
    if hab_area_layer is None:
        raise ValueError("Missing layer: hab_area")

    area = hab_area_layer.copy()
    area = area.rename(columns={"rgn_id": "rgn_id", "area_km2": "area_km2"})
    area = area[["rgn_id", "area_km2"]]

    # STEP 3: Merge hab with area
    hab = hab.merge(area, on="rgn_id", how="left")

    # STEP 4: Calculate reference point: max(value/area_km2) per region-habitat
    p_ref = hab.copy()
    p_ref["por"] = p_ref["value"] / p_ref["area_km2"]
    p_ref = p_ref.groupby(["rgn_id", "habitat"]).agg({"por": "max"}).reset_index()
    p_ref = p_ref.rename(columns={"por": "ref"})
    p_ref = p_ref[["rgn_id", "habitat", "ref"]]

    # STEP 5: Filter out habitats where all values are 0 for years 2018-2022
    com_hab = hab.copy()
    com_hab = com_hab.groupby(["rgn_id", "area_km2", "habitat"]).filter(
        lambda x: not all((x["value"] == 0) & (x["year"].isin(range(2018, 2023))))
    )

    # STEP 6: Count number of habitats per region
    com_h1 = []
    for rgn_id in hab["rgn_id"].unique():
        com = com_hab[com_hab["rgn_id"] == rgn_id]
        n_h = com["habitat"].nunique()
        com_h1.append({"rgn_id": rgn_id, "n_h": n_h})
    com_h1 = pd.DataFrame(com_h1)
    com_h1 = com_h1[~com_h1["n_h"].isna()]

    # STEP 7: Calculate scores
    hab_scores = com_hab.merge(p_ref, on=["rgn_id", "habitat"], how="left")
    # area_km2 is already in com_hab from earlier merge

    scores_hab = hab_scores.copy()
    scores_hab["Cc"] = scores_hab["value"] / scores_hab["area_km2"]
    scores_hab["C"] = scores_hab["Cc"] / scores_hab["ref"]
    scores_hab = scores_hab.groupby(["rgn_id", "year"]).agg({"C": "sum"}).reset_index()
    scores_hab = scores_hab.rename(columns={"C": "c_sum"})
    scores_hab = scores_hab.merge(com_h1, on="rgn_id", how="outer")
    scores_hab["status"] = (scores_hab["c_sum"] / scores_hab["n_h"]) * 100

    # STEP 8: Extract status for scenario year
    status_hab = scores_hab[scores_hab["year"] == scenario_year].copy()
    status_hab["score"] = status_hab["status"].round(4)
    status_hab = status_hab.rename(columns={"rgn_id": "region_id"})
    status_hab["dimension"] = "status"
    status_hab = status_hab[["region_id", "score", "dimension"]]

    # STEP 9: Calculate trend
    trend_years = list(range(scenario_year - 4, scenario_year + 1))

    r_trend = calculate_trend(status_data=scores_hab, trend_years=trend_years)

    return status_hab, r_trend
