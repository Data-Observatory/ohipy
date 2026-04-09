"""SP Goal - Sense of Place

Post-index goal that aggregates ICO (Iconic Species) and LSP (Lasting Special Places)
scores using a simple mean.

Algorithm:
1. Filter ICO and LSP scores (exclude pressures/resilience dimensions)
2. Calculate simple mean per region and dimension
3. Return aggregated SP scores
"""

from __future__ import annotations

from typing import cast

import polars as pl


def SP(layers: dict[str, object], scores: pl.DataFrame) -> pl.DataFrame:  # noqa: N802
    """
    Calculate SP (Sense of Place) goal by aggregating ICO and LSP scores.

    This is a post-index goal that combines pre-calculated ICO and LSP scores
    using a simple mean (equal weighting).

    Args:
        layers: Layers dictionary from load_layers()
        scores: DataFrame with existing goal scores (must include ICO and LSP)
                Columns: [region_id, goal, dimension, score]

    Returns:
        DataFrame: Updated scores with SP goal added
                   Columns: [region_id, goal, dimension, score]
    """
    _ = cast(dict[str, object], layers)

    # STEP 1: Filter ICO and LSP scores
    # Exclude pressures and resilience dimensions (only status and trend)
    s = scores.filter(
        pl.col("goal").is_in(["ICO", "LSP"])
        & ~pl.col("dimension").is_in(["pressures", "resilience"])
    )

    # STEP 2: Calculate simple mean per region and dimension
    sp_scores = (
        s.group_by(["region_id", "dimension"])
        .agg(pl.col("score").mean())
        .with_columns(goal=pl.lit("SP"))
        .select(["goal", "dimension", "region_id", "score"])
    )

    scores_updated = pl.concat(
        [scores.select(["goal", "dimension", "region_id", "score"]), sp_scores],
        how="vertical_relaxed",
    )

    return scores_updated
