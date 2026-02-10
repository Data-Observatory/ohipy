"""CS Goal - Carbon Sequestration

Calculates status and trend for the Carbon Sequestration goal based on habitat extent.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 436-532):
1. Load habitat extension data (filter to 3 habitats: Macrocystis, Pastos marinos, Marismas y humedales)
2. Filter out habitats with total m2 = 0 per region-habitat
3. Calculate reference point: max(m2) per region-habitat
4. Calculate weighted scores using habitat coefficients
5. Calculate status: (sum(h*w*m2) / sum(w*m2)) * 100
6. Calculate trend using linear regression
"""

import pandas as pd
import numpy as np


def CS(layers):
    """
    Calculate CS (Carbon Sequestration) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    # Import here to avoid circular imports
    from ohi.calculate import calculate_trend

    # Get scenario year
    scen_year = layers["data"].get("scenario_year", 2024)
    trend_years = list(range(scen_year - 4, scen_year + 1))

    # STEP 1: Load habitat extension data
    cs_layer = layers["data"].get("cs_habitat_extension")
    if cs_layer is None:
        raise ValueError("Missing layer: cs_habitat_extension")

    cs = cs_layer.copy()
    # Columns: rgn_id, habitat, year, value
    cs = cs.rename(columns={"value": "m2"})

    # Filter to specific habitats
    cs = cs[
        cs["habitat"].isin(["Macrocystis", "Pastos marinos", "Marismas y humedales"])
    ]
    cs["rgn_id"] = cs["rgn_id"].astype(float)

    # STEP 2: Load area data
    area_layer = layers["data"].get("cs_area")
    if area_layer is None:
        raise ValueError("Missing layer: cs_area")

    area = area_layer.copy()
    # Columns: rgn_id, area_km2
    area = area.rename(columns={"area_km2": "m2"})
    area["rgn_id"] = area["rgn_id"].astype(float)

    # STEP 3: Define habitat coefficients
    coef = pd.DataFrame(
        {
            "habitat": ["Macrocystis", "Pastos marinos", "Marismas y humedales"],
            "w": [133.1, 138, 129.8],
        }
    )

    # STEP 4: Filter out habitats with sum(m2) = 0 per region-habitat
    # Group by rgn_id and habitat, calculate sum
    cs = (
        cs.groupby(["rgn_id", "habitat"])
        .apply(lambda x: x.assign(f=x["m2"].sum()))
        .reset_index(drop=True)
    )

    # Filter to only keep habitats where f > 0
    cs["m22"] = cs.apply(lambda row: row["f"] if row["f"] > 0 else np.nan, axis=1)
    cs = cs[~cs["m22"].isna()]
    cs = cs[["rgn_id", "habitat", "year", "m2"]]

    # STEP 5: Calculate reference point (max m2 per region-habitat)
    p_ref = cs.groupby(["rgn_id", "habitat"])["m2"].max().reset_index()
    p_ref = p_ref.rename(columns={"m2": "p_ref"})
    p_ref = p_ref[p_ref["p_ref"] > 0]

    # STEP 6: Calculate scores
    cs_scores = cs.merge(p_ref, on=["rgn_id", "habitat"], how="left")
    cs_scores["h"] = cs_scores["m2"] / cs_scores["p_ref"]
    cs_scores = cs_scores[["rgn_id", "habitat", "h", "year"]]

    # Join with coefficients
    cs_scores = cs_scores.merge(coef, on="habitat", how="left")

    # Join back with cs to get m2
    cs_scores = cs_scores.merge(cs, on=["rgn_id", "habitat", "year"], how="left")

    # Calculate A and B
    cs_scores["A"] = cs_scores["h"] * cs_scores["w"] * cs_scores["m2"]
    cs_scores["B"] = cs_scores["w"] * cs_scores["m2"]

    # Sum A and B per region-year
    cs_scores = (
        cs_scores.groupby(["rgn_id", "year"])
        .agg({"A": lambda x: x.sum(), "B": lambda x: x.sum()})
        .reset_index()
    )

    # Calculate status
    cs_scores["status"] = (cs_scores["A"] / cs_scores["B"]) * 100

    # STEP 7: Extract status for scenario year
    cs_status = cs_scores[cs_scores["year"] == scen_year].copy()
    cs_status = cs_status.rename(columns={"rgn_id": "region_id", "status": "score"})
    cs_status["dimension"] = "status"
    cs_status = cs_status[["region_id", "score", "dimension"]]

    # STEP 8: Calculate trend
    cs_trend = calculate_trend(
        status_data=cs_scores, trend_years=trend_years, default_trend=None
    )
    cs_trend["dimension"] = "trend"

    return cs_status, cs_trend
