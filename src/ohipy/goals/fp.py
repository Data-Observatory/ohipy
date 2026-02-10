"""FP Goal - Food Provision

Post-index goal that aggregates FIS (Fisheries) and MAR (Mariculture) scores
using region-specific weighted means.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 259-294):
1. Load fp_wildcaught_weight layer (w_fis per region)
2. Calculate w_mar = 1 - w_fis
3. Filter FIS and MAR scores (exclude pressures/resilience dimensions)
4. Apply weights: FIS uses w_fis, MAR uses w_mar
5. Calculate weighted mean per region and dimension
6. Return aggregated FP scores
"""

import pandas as pd
import numpy as np


def FP(layers, scores):
    """
    Calculate FP (Food Provision) goal by aggregating FIS and MAR scores.

    This is a post-index goal that combines pre-calculated FIS and MAR scores
    using region-specific weights based on wild-caught vs. mariculture production.

    Args:
        layers: Layers dictionary from load_layers()
        scores: DataFrame with existing goal scores (must include FIS and MAR)
                Columns: [region_id, goal, dimension, score]

    Returns:
        DataFrame: Updated scores with FP goal added
                   Columns: [region_id, goal, dimension, score]
    """
    # Get scenario year from layers data
    scen_year = layers["data"].get("scenario_year", 2024)

    # STEP 1: Load wild-caught weight layer
    w_layer = layers["data"].get("fp_wildcaught_weight")
    if w_layer is None:
        raise ValueError("Missing layer: fp_wildcaught_weight")

    w = w_layer.copy()
    # Standardize column names (rgn_id → region_id, val_num → w_fis)
    w = w.rename(columns={"rgn_id": "region_id", "val_num": "w_fis"})

    # Filter out NA weights
    w = w[w["w_fis"].notna()]
    w = w[["region_id", "w_fis"]]

    # STEP 2: Filter FIS and MAR scores
    # Exclude pressures and resilience dimensions (only status and trend)
    s = scores[
        (scores["goal"].isin(["FIS", "MAR"]))
        & (~scores["dimension"].isin(["pressures", "resilience"]))
    ].copy()

    # STEP 3: Merge with weights
    s = s.merge(w, on="region_id", how="left")

    # Calculate mariculture weight (complement of wild-caught)
    s["w_mar"] = 1 - s["w_fis"]

    # STEP 4: Apply appropriate weight based on goal
    # FIS uses w_fis, MAR uses w_mar
    s["weight"] = s.apply(
        lambda row: row["w_fis"] if row["goal"] == "FIS" else row["w_mar"], axis=1
    )

    # STEP 5: Calculate weighted mean per region and dimension
    # Handle NaN properly: ignore NaN scores even if they have weight
    def weighted_mean_with_nan(group):
        scores = group["score"].values.astype(float)
        weights = group["weight"].values.astype(float)

        # Create mask for valid (non-NaN) scores
        valid_mask = ~np.isnan(scores)

        if valid_mask.sum() == 0:
            # All scores are NaN
            return np.nan

        # Filter to valid scores and their weights
        valid_scores = scores[valid_mask]
        valid_weights = weights[valid_mask]

        # If all valid weights are 0, return NaN
        if valid_weights.sum() == 0:
            return np.nan

        # Calculate weighted mean of valid scores
        return np.average(valid_scores, weights=valid_weights)

    # Group by region_id and dimension, calculate weighted mean
    fp_scores = (
        s.groupby(["region_id", "dimension"])
        .apply(weighted_mean_with_nan, include_groups=False)
        .reset_index()
        .rename(columns={0: "score"})
    )

    # Add goal column
    fp_scores["goal"] = "FP"

    # Reorder columns to match expected format
    fp_scores = fp_scores[["region_id", "goal", "dimension", "score"]]

    # STEP 6: Append FP scores to existing scores
    # R behavior in ohi-science-chl/comunas/conf/functions.R returns FP scores twice
    # via rbind(scores, s) after already appending s once.
    scores_updated = pd.concat([scores, fp_scores, fp_scores], ignore_index=True)
    return scores_updated
