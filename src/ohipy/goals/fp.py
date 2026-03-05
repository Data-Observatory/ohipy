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

import numpy as np
import pandas as pd
import polars as pl

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
    s["weight"] = np.where(s["goal"] == "FIS", s["w_fis"], s["w_mar"])

    # STEP 5: Calculate weighted mean per region and dimension using Polars
    # Convert to Polars for efficient weighted mean calculation
    s_pl = pl.DataFrame(s)
    
    # Calculate weighted mean with proper NaN handling
    fp_scores_pl = (
        s_pl
        .with_columns([
            pl.col("score").cast(pl.Float64).alias("score"),
            pl.col("weight").cast(pl.Float64).alias("weight"),
        ])
        .with_columns([
            (pl.col("score") * pl.col("weight")).alias("_weighted"),
        ])
        .group_by(["region_id", "dimension"])
        .agg([
            pl.col("_weighted").sum().alias("_weighted_sum"),
            pl.col("weight").sum().alias("_weight_sum"),
        ])
        .with_columns([
            pl.when(pl.col("_weight_sum") == 0)
            .then(None)
            .otherwise(pl.col("_weighted_sum") / pl.col("_weight_sum"))
            .alias("score"),
        ])
        .select(["region_id", "dimension", "score"])
    )
    
    # Convert back to pandas
    fp_scores = fp_scores_pl.to_pandas()

    # Add goal column
    fp_scores["goal"] = "FP"

    # Reorder columns to match expected format
    fp_scores = fp_scores[["region_id", "goal", "dimension", "score"]]

    # STEP 6: Append FP scores to existing scores
    # R behavior in ohi-science-chl/comunas/conf/functions.R returns FP scores twice
    # via rbind(scores, s) after already appending s once.
    # This was fixed on 2026-02-26, as per agreement with R code author, to only append once.
    scores_updated = pd.concat([scores, fp_scores], ignore_index=True)
    return scores_updated
