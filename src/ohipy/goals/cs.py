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


def CS(layers):
    """
    Calculate CS (Carbon Sequestration) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a polars DataFrame with columns:
               [region_id, score, dimension]
    """
    # Import here to avoid circular imports
    from ohipy.calculate import calculate_trend

    # Get scenario year
    scen_year = layers["data"].get("scenario_year", 2024)
    trend_years = list(range(scen_year - 4, scen_year + 1))

    # STEP 1: Load habitat extension data
    cs_layer = layers["data"].get("cs_habitat_extension")
    if cs_layer is None:
        raise ValueError("Missing layer: cs_habitat_extension")

    # Convert to polars if needed
    if hasattr(cs_layer, "to_pandas"):
        # Already polars
        cs = cs_layer.clone()
    else:
        # Convert from pandas
        cs = pl.from_pandas(cs_layer)

    # Columns: rgn_id, habitat, year, value
    cs = cs.rename({"value": "m2"})

    # Filter to specific habitats
    cs = cs.filter(
        pl.col("habitat").is_in(["Macrocystis", "Pastos marinos", "Marismas y humedales"])
    )
    cs = cs.with_columns(pl.col("rgn_id").cast(pl.Float64))

    # STEP 2: Load area data
    area_layer = layers["data"].get("cs_area")
    if area_layer is None:
        raise ValueError("Missing layer: cs_area")

    # Convert to polars if needed
    if hasattr(area_layer, "to_pandas"):
        area = area_layer.clone()
    else:
        area = pl.from_pandas(area_layer)

    # Columns: rgn_id, area_km2
    area = area.rename({"area_km2": "m2"})
    area = area.with_columns(pl.col("rgn_id").cast(pl.Float64))

    # STEP 3: Define habitat coefficients
    coef = pl.DataFrame(
        {
            "habitat": ["Macrocystis", "Pastos marinos", "Marismas y humedales"],
            "w": [133.1, 138.0, 129.8],
        }
    )

    # STEP 4: Filter out habitats with sum(m2) = 0 per region-habitat
    cs = cs.with_columns(
        pl.col("m2").sum().over(["rgn_id", "habitat"]).alias("f"),
    )
    cs = cs.filter(pl.col("f") > 0)
    cs = cs.select(["rgn_id", "habitat", "year", "m2"])

    # STEP 5: Calculate reference point (max m2 per region-habitat)
    p_ref = cs.group_by(["rgn_id", "habitat"]).agg(
        pl.col("m2").max().alias("p_ref"),
    )
    p_ref = p_ref.filter(pl.col("p_ref") > 0)

    # STEP 6: Calculate scores
    cs_scores = cs.join(p_ref, on=["rgn_id", "habitat"], how="left")
    cs_scores = cs_scores.with_columns(
        (pl.col("m2") / pl.col("p_ref")).alias("h"),
    )
    cs_scores = cs_scores.select(["rgn_id", "habitat", "h", "year"])

    # Join with coefficients
    cs_scores = cs_scores.join(coef, on="habitat", how="left")

    # Join back with cs to get m2
    cs_scores = cs_scores.join(cs, on=["rgn_id", "habitat", "year"], how="left")

    # Calculate A and B
    cs_scores = cs_scores.with_columns(
        [
            (pl.col("h") * pl.col("w") * pl.col("m2")).alias("A"),
            (pl.col("w") * pl.col("m2")).alias("B"),
        ]
    )

    # Sum A and B per region-year
    cs_scores = cs_scores.group_by(["rgn_id", "year"]).agg(
        [
            pl.col("A").sum().alias("A"),
            pl.col("B").sum().alias("B"),
        ]
    )

    # Calculate status
    cs_scores = cs_scores.with_columns(
        ((pl.col("A") / pl.col("B")) * 100).alias("status"),
    )

    # STEP 7: Extract status for scenario year
    cs_status = cs_scores.filter(pl.col("year") == scen_year)
    cs_status = cs_status.rename({"rgn_id": "region_id"})
    cs_status = cs_status.rename({"status": "score"})
    cs_status = cs_status.with_columns(pl.lit("status").alias("dimension"))
    cs_status = cs_status.select(["region_id", "score", "dimension"])

    # STEP 8: Calculate trend
    cs_trend = calculate_trend(status_data=cs_scores, trend_years=trend_years, default_trend=None)
    cs_trend = cs_trend.with_columns(pl.lit("trend").alias("dimension"))
    cs_trend = cs_trend.select(["region_id", "score", "dimension"])

    return cs_status, cs_trend
