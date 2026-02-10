"""SP Goal - Sense of Place

Post-index goal that aggregates ICO (Iconic Species) and LSP (Lasting Special Places)
scores using a simple mean.

Algorithm:
1. Filter ICO and LSP scores (exclude pressures/resilience dimensions)
2. Calculate simple mean per region and dimension
3. Return aggregated SP scores
"""

import pandas as pd
import numpy as np


def SP(layers, scores):
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
    # STEP 1: Filter ICO and LSP scores
    # Exclude pressures and resilience dimensions (only status and trend)
    s = scores[
        (scores["goal"].isin(["ICO", "LSP"]))
        & (~scores["dimension"].isin(["pressures", "resilience"]))
    ].copy()

    # STEP 2: Calculate simple mean per region and dimension
    # Group by region_id and dimension, calculate mean
    sp_scores = (
        s.groupby(["region_id", "dimension"]).agg({"score": "mean"}).reset_index()
    )

    # Add goal column
    sp_scores["goal"] = "SP"

    # Reorder columns to match expected format
    sp_scores = sp_scores[["region_id", "goal", "dimension", "score"]]

    # STEP 3: Append SP scores to existing scores
    scores_updated = pd.concat([scores, sp_scores], ignore_index=True)

    return scores_updated
