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
    # STEP 1: Load wild-caught weight layer
    w_layer = layers["data"].get("fp_wildcaught_weight")
    if w_layer is None:
        raise ValueError("Missing layer: fp_wildcaught_weight")

    # Convert to polars if needed
    if not isinstance(w_layer, pl.DataFrame):
        w = pl.DataFrame(w_layer)
    else:
        w = w_layer.clone()

    # Standardize column names (rgn_id → region_id)
    # Layer may have val_num or w_fis as the value column
    rename_map = {"rgn_id": "region_id"}
    if "val_num" in w.columns:
        rename_map["val_num"] = "w_fis"
    w = w.rename(rename_map)

    w = w.with_columns(pl.col("region_id").cast(pl.Int64))
    w = w.filter(pl.col("w_fis").is_not_null()).select(["region_id", "w_fis"])

    if not isinstance(scores, pl.DataFrame):
        s = pl.DataFrame(scores)
    else:
        s = scores.clone()

    s = s.with_columns(pl.col("region_id").cast(pl.Int64))
    s = s.filter(
        pl.col("goal").is_in(["FIS", "MAR"])
        & ~pl.col("dimension").is_in(["pressures", "resilience"])
    )

    # STEP 3: Join with weights
    s = s.join(w, on="region_id", how="left")

    # Calculate mariculture weight (complement of wild-caught)
    # Apply appropriate weight based on goal: FIS uses w_fis, MAR uses w_mar
    s = s.with_columns(
        [
            (1 - pl.col("w_fis")).alias("w_mar"),
        ]
    ).with_columns(
        [
            pl.when(pl.col("goal") == "FIS")
            .then(pl.col("w_fis"))
            .otherwise(pl.col("w_mar"))
            .alias("weight"),
        ]
    )

    # STEP 4: Calculate weighted mean per region and dimension
    # Filter out NaN scores first (matching R's weighted.mean with na.rm=TRUE)
    s = s.filter(pl.col("score").is_finite())

    fp_scores = (
        s.with_columns(
            [
                pl.col("score").cast(pl.Float64).alias("score"),
                pl.col("weight").cast(pl.Float64).alias("weight"),
            ]
        )
        .with_columns(
            [
                (pl.col("score") * pl.col("weight")).alias("_weighted"),
            ]
        )
        .group_by(["region_id", "dimension"])
        .agg(
            [
                pl.col("_weighted").sum().alias("_weighted_sum"),
                pl.col("weight").sum().alias("_weight_sum"),
            ]
        )
        .with_columns(
            [
                pl.when(pl.col("_weight_sum") == 0)
                .then(None)
                .otherwise(pl.col("_weighted_sum") / pl.col("_weight_sum"))
                .alias("score"),
            ]
        )
        .with_columns([pl.lit("FP").alias("goal")])
        .select(["goal", "dimension", "region_id", "score"])
    )

    # STEP 5: Append FP scores to existing scores
    # R behavior in ohi-science-chl/comunas/conf/functions.R returns FP scores twice
    # via rbind(scores, s) after already appending s once.
    # This was fixed on 2026-02-26, as per agreement with R code author, to only append once.
    scores_pl = scores if isinstance(scores, pl.DataFrame) else pl.DataFrame(scores)
    scores_updated = pl.concat(
        [scores_pl.select(["goal", "dimension", "region_id", "score"]), fp_scores],
        how="vertical_relaxed",
    )
    return scores_updated
