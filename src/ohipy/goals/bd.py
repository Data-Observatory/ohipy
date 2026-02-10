"""BD Goal - Biodiversity

Post-index goal that aggregates HAB (Habitats) and SPP (Species) scores
using a simple mean.

Algorithm:
1. Filter HAB and SPP scores (exclude pressures/resilience dimensions)
2. Calculate simple mean per region and dimension
3. Return aggregated BD scores
"""

import pandas as pd
import numpy as np


def BD(layers, scores):
    """
    Calculate BD (Biodiversity) goal by aggregating HAB and SPP scores.

    This is a post-index goal that combines pre-calculated HAB and SPP scores
    using a simple mean (equal weighting).

    Args:
        layers: Layers dictionary from load_layers()
        scores: DataFrame with existing goal scores (must include HAB and SPP)
                Columns: [region_id, goal, dimension, score]

    Returns:
        DataFrame: Updated scores with BD goal added
                   Columns: [region_id, goal, dimension, score]
    """
    # STEP 1: Filter HAB and SPP scores
    # Exclude pressures and resilience dimensions (only status and trend)
    s = scores[
        (scores["goal"].isin(["HAB", "SPP"]))
        & (~scores["dimension"].isin(["pressures", "resilience"]))
    ].copy()

    # STEP 2: Calculate simple mean per region and dimension
    # Group by region_id and dimension, calculate mean
    bd_scores = (
        s.groupby(["region_id", "dimension"]).agg({"score": "mean"}).reset_index()
    )

    # Add goal column
    bd_scores["goal"] = "BD"

    # Reorder columns to match expected format
    bd_scores = bd_scores[["region_id", "goal", "dimension", "score"]]

    # STEP 3: Append BD scores to existing scores
    scores_updated = pd.concat([scores, bd_scores], ignore_index=True)

    return scores_updated
