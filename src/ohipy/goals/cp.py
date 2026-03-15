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

import numpy as np
import polars as pl


def _calculate_habitat_trend_polars(df: pl.DataFrame) -> pl.DataFrame:
    results = []

    for (rgn_id, habitat), group in df.group_by(["rgn_id", "habitat"]):
        if len(group) < 2:
            results.append({"rgn_id": rgn_id, "habitat": habitat, "trend": None})
            continue

        years = group["year"].to_numpy()
        km2_vals = group["km2"].to_numpy()

        std_km2 = np.std(km2_vals)
        if std_km2 == 0:
            results.append({"rgn_id": rgn_id, "habitat": habitat, "trend": None})
            continue

        slope = np.polyfit(years, km2_vals, 1)[0]
        trend_val = slope * np.std(years) / std_km2 * 5
        trend_val = max(-1.0, min(1.0, trend_val))

        results.append({"rgn_id": rgn_id, "habitat": habitat, "trend": trend_val})

    return pl.DataFrame(results)


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
    extent_layer = layers["data"].get("cp_habitat_extension")
    if extent_layer is None:
        raise ValueError("Missing layer: cp_habitat_extension")

    # Convert to polars if needed
    if hasattr(extent_layer, "to_pandas"):
        # Already polars
        extent = extent_layer.clone()
    else:
        # Convert pandas to polars
        extent = pl.from_pandas(extent_layer)

    # Columns: rgn_id, habitat, year, value
    extent = extent.rename({"value": "km2"})

    # Filter to last 5 years
    extent = extent.filter(pl.col("year") >= (scen_year - 4))
    extent = extent.select(["year", "rgn_id", "habitat", "km2"])

    # STEP 2: Calculate trend per region-habitat
    trend = _calculate_habitat_trend_polars(extent)

    # STEP 3: Calculate health per region-habitat
    # Get max km2 per region-habitat
    health_agg = extent.group_by(["rgn_id", "habitat"]).agg(pl.col("km2").max().alias("km2_max"))

    # Join back to calculate health
    health = extent.join(health_agg, on=["rgn_id", "habitat"], how="left")
    health = health.with_columns((pl.col("km2") / pl.col("km2_max")).alias("health"))

    # STEP 4: Merge extent, health, trend
    d = extent.join(
        health.select(["year", "rgn_id", "habitat", "health"]),
        on=["year", "rgn_id", "habitat"],
        how="left",
    )
    d = d.join(trend, on=["rgn_id", "habitat"], how="left")

    # STEP 5: Define habitat ranks
    habitat_rank = pl.DataFrame(
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

    d = d.join(habitat_rank, on="habitat", how="outer")

    # STEP 6: Calculate f1
    d = d.with_columns((pl.col("rank") * pl.col("health") * pl.col("km2")).alias("f1"))

    # STEP 7: Calculate status (year == 2024)
    scores_CP_status = (
        d.filter(
            pl.col("rank").is_not_null()
            & pl.col("health").is_not_null()
            & ~pl.col("health").is_nan()
            & pl.col("km2").is_not_null()
            & (pl.col("year") == 2024)
        )
        .group_by("rgn_id")
        .agg(
            (
                pl.min_horizontal(
                    1.0, pl.col("f1").sum() / (pl.col("km2").sum() * pl.col("rank").max())
                )
                * 100
            ).alias("score")
        )
        .with_columns(pl.lit("status").alias("dimension"))
    )

    # STEP 8: Calculate trend
    d_trend = d.filter(
        pl.col("rank").is_not_null() & pl.col("trend").is_not_null() & pl.col("km2").is_not_null()
    )

    if len(d_trend) > 0:
        trend_scores = (
            d_trend.group_by("rgn_id")
            .agg(
                (
                    (pl.col("rank") * pl.col("trend") * pl.col("km2")).sum()
                    / (pl.col("km2") * pl.col("rank")).sum()
                ).alias("score")
            )
            .with_columns(pl.lit("trend").alias("dimension"))
        )

        scores_CP = pl.concat([scores_CP_status, trend_scores])
    else:
        scores_CP = scores_CP_status

    # Finalize
    scores_CP = scores_CP.rename({"rgn_id": "region_id"})
    scores_CP = scores_CP.select(["region_id", "dimension", "score"])

    # Split into status and trend
    status_df = scores_CP.filter(pl.col("dimension") == "status").clone()
    trend_df = scores_CP.filter(pl.col("dimension") == "trend").clone()

    return status_df, trend_df
