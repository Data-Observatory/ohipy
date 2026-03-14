"""BD Goal - Biodiversity (Polars-native)

Post-index goal aggregating HAB and SPP scores using simple mean.
"""

import polars as pl


def BD(layers, scores):
    """Calculate BD (Biodiversity) by aggregating HAB and SPP scores.

    Args:
        layers: Layers dictionary
        scores: polars DataFrame with columns [region_id, goal, dimension, score]

    Returns:
        polars DataFrame: Updated scores with BD added
    """
    s = scores.filter(
        pl.col("goal").is_in(["HAB", "SPP"])
        & ~pl.col("dimension").is_in(["pressures", "resilience"])
    )

    bd_scores = (
        s.group_by(["region_id", "dimension"])
        .agg(pl.col("score").mean())
        .with_columns(pl.lit("BD").alias("goal"))
        .select(["goal", "dimension", "region_id", "score"])
    )

    return pl.concat(
        [scores.select(["goal", "dimension", "region_id", "score"]), bd_scores],
        how="vertical_relaxed",
    )
