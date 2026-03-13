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

import numpy as np
import polars as pl
import pandas as pd


def _ensure_pandas(df):
    """Convert polars DataFrame to pandas if needed, pass through pandas unchanged."""
    if df is None:
        return None
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    return df


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
    from ohipy.calculate import calculate_trend

    # Get scenario year
    scen_year = layers["data"].get("scenario_year", 2024)
    trend_years = list(range(scen_year - 4, scen_year + 1))

    # STEP 1: Load habitat extension data
    cs_layer = _ensure_pandas(layers["data"].get("cs_habitat_extension"))
    if cs_layer is None:
        raise ValueError("Missing layer: cs_habitat_extension")

    cs = cs_layer.copy()
    # Columns: rgn_id, habitat, year, value
    cs = cs.rename(columns={"value": "m2"})

    # Filter to specific habitats
    cs = cs[cs["habitat"].isin(["Macrocystis", "Pastos marinos", "Marismas y humedales"])]
    cs["rgn_id"] = cs["rgn_id"].astype(float)

    # STEP 2: Load area data
    area_layer = _ensure_pandas(layers["data"].get("cs_area"))
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
    # Use Polars for group-level sum calculation
    cs_pl = pl.DataFrame(cs)
    cs_pl = cs_pl.with_columns(
        [
            pl.col("m2").sum().over(["rgn_id", "habitat"]).alias("f"),
        ]
    )
    cs_pl = cs_pl.filter(pl.col("f") > 0)
    cs_pl = cs_pl.select(["rgn_id", "habitat", "year", "m2"])

    # STEP 5: Calculate reference point (max m2 per region-habitat)
    p_ref_pl = cs_pl.group_by(["rgn_id", "habitat"]).agg(
        [
            pl.col("m2").max().alias("p_ref"),
        ]
    )
    p_ref_pl = p_ref_pl.filter(pl.col("p_ref") > 0)

    # STEP 6: Calculate scores using Polars
    cs_scores_pl = cs_pl.join(p_ref_pl, on=["rgn_id", "habitat"], how="left")
    cs_scores_pl = cs_scores_pl.with_columns(
        [
            (pl.col("m2") / pl.col("p_ref")).alias("h"),
        ]
    )
    cs_scores_pl = cs_scores_pl.select(["rgn_id", "habitat", "h", "year"])

    # Join with coefficients
    coef_pl = pl.DataFrame(coef)
    cs_scores_pl = cs_scores_pl.join(coef_pl, on="habitat", how="left")

    # Join back with cs to get m2
    cs_scores_pl = cs_scores_pl.join(cs_pl, on=["rgn_id", "habitat", "year"], how="left")

    # Calculate A and B
    cs_scores_pl = cs_scores_pl.with_columns(
        [
            (pl.col("h") * pl.col("w") * pl.col("m2")).alias("A"),
            (pl.col("w") * pl.col("m2")).alias("B"),
        ]
    )

    # Sum A and B per region-year
    cs_scores_pl = cs_scores_pl.group_by(["rgn_id", "year"]).agg(
        [
            pl.col("A").sum().alias("A"),
            pl.col("B").sum().alias("B"),
        ]
    )

    # Calculate status
    cs_scores_pl = cs_scores_pl.with_columns(
        [
            ((pl.col("A") / pl.col("B")) * 100).alias("status"),
        ]
    )
    cs_scores = cs_scores_pl.to_pandas()

    # STEP 7: Extract status for scenario year
    cs_status = cs_scores[cs_scores["year"] == scen_year].copy()
    cs_status = cs_status.rename(columns={"rgn_id": "region_id", "status": "score"})
    cs_status["dimension"] = "status"
    cs_status = cs_status[["region_id", "score", "dimension"]]

    # STEP 8: Calculate trend
    cs_trend = calculate_trend(status_data=cs_scores, trend_years=trend_years, default_trend=None)
    cs_trend["dimension"] = "trend"

    return cs_status, cs_trend
