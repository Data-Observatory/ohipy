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

import polars as pl

from ..calculate import calculate_trend


def HAB(layers):
    """
    Calculate HAB (Habitats) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a polars DataFrame with columns:
               [region_id, score, dimension]
    """
    scenario_year = layers["data"]["scenario_year"]

    # STEP 1: Load hab_extension layer
    hab_extension_layer = layers["data"].get("hab_extension")
    if hab_extension_layer is None:
        raise ValueError("Missing layer: hab_extension")

    hab = hab_extension_layer.clone()
    hab = hab.select(["rgn_id", "year", "habitat", "value"])

    # STEP 2: Load hab_area layer
    hab_area_layer = layers["data"].get("hab_area")
    if hab_area_layer is None:
        raise ValueError("Missing layer: hab_area")

    area = hab_area_layer.clone()
    area = area.select(["rgn_id", "area_km2"])

    # STEP 3: Merge hab with area
    hab = hab.join(area, on="rgn_id", how="left")

    # STEP 4: Calculate reference point: max(value/area_km2) per region-habitat
    p_ref = hab.clone()
    p_ref = p_ref.with_columns((pl.col("value") / pl.col("area_km2")).alias("por"))
    p_ref = p_ref.group_by(["rgn_id", "habitat"]).agg(pl.col("por").max().alias("ref"))
    p_ref = p_ref.select(["rgn_id", "habitat", "ref"])

    # STEP 5: Filter out habitats where all values are 0 for years 2018-2022
    # Keep groups where NOT all rows have (value==0 AND year in 2018-2022)
    com_hab = hab.filter(
        ~(
            ((pl.col("value") == 0) & pl.col("year").is_in(range(2018, 2023)))
            .all()
            .over(["rgn_id", "habitat"])
        )
    )

    # STEP 6: Count number of habitats per region
    com_h1 = (
        com_hab.group_by("rgn_id")
        .agg(pl.col("habitat").n_unique().alias("n_h"))
        .filter(pl.col("n_h").is_not_null())
    )

    # STEP 7: Calculate scores
    hab_scores = com_hab.join(p_ref, on=["rgn_id", "habitat"], how="left")

    scores_hab = hab_scores.with_columns((pl.col("value") / pl.col("area_km2")).alias("Cc"))
    scores_hab = scores_hab.with_columns(
        pl.when(pl.col("ref") == 0).then(0.0).otherwise(pl.col("Cc") / pl.col("ref")).alias("C")
    )
    scores_hab = scores_hab.group_by(["rgn_id", "year"]).agg(pl.col("C").sum().alias("c_sum"))
    scores_hab = scores_hab.join(com_h1, on="rgn_id", how="full")
    scores_hab = scores_hab.with_columns(((pl.col("c_sum") / pl.col("n_h")) * 100).alias("status"))

    # STEP 8: Extract status for scenario year
    status_hab = scores_hab.filter(pl.col("year") == scenario_year).clone()
    status_hab = status_hab.with_columns(pl.col("status").round(4).alias("score"))
    status_hab = status_hab.rename({"rgn_id": "region_id"})
    status_hab = status_hab.with_columns(pl.lit("status").alias("dimension"))
    status_hab = status_hab.select(["region_id", "score", "dimension"])

    # STEP 9: Calculate trend
    trend_years = list(range(scenario_year - 4, scenario_year + 1))

    r_trend = calculate_trend(status_data=scores_hab, trend_years=trend_years)

    return status_hab, r_trend
