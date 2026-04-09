"""BD Goal - Biodiversity (Polars-native)

Post-index goal aggregating HAB and SPP scores using simple mean.
"""

from __future__ import annotations

from typing import cast

import polars as pl


def BD(layers: dict[str, object], scores: pl.DataFrame) -> pl.DataFrame:  # noqa: N802
    """Calculate BD (Biodiversity) by aggregating HAB and SPP scores.

    Args:
        layers: Layers dictionary
        scores: polars DataFrame with columns [region_id, goal, dimension, score]

    Returns:
        polars DataFrame: Updated scores with BD added
    """
    _ = cast(dict[str, object], layers)

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
