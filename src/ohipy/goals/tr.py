"""TR Goal - Tourism & Recreation

Calculates status and trend for the Tourism & Recreation goal.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 621-700):
1. Load tourism jobs %, sustainability scores, and correction factor
2. Join tourism and sustainability, fill missing s_score with 0.5
3. Calculate Xtr = ep * s_score
4. Apply correction factor: xtr = Xtr * factor
5. Calculate reference points per year: p_max (90th percentile), p_min (0th percentile)
6. Calculate status: (xtr - p_min) / (p_max - p_min), capped at 1
7. Extract status for scenario year
8. Calculate trend using linear regression
"""

import polars as pl


def TR(layers):
    """
    Calculate TR (Tourism & Recreation) goal status and trend.

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

    # STEP 1: Load tourism jobs percentage
    tourism_layer = layers["data"].get("tr_jobs_pct_tourism")
    if tourism_layer is None:
        raise ValueError("Missing layer: tr_jobs_pct_tourism")

    tourism = tourism_layer.select(["rgn_id", "year", "ep"])

    # STEP 2: Load sustainability scores
    sustain_layer = layers["data"].get("tr_sustainability")
    if sustain_layer is None:
        raise ValueError("Missing layer: tr_sustainability")

    sustain = sustain_layer.select(["rgn_id", "year", "s_score"])

    # STEP 3: Load correction factor
    factor_layer = layers["data"].get("tr_factor")
    if factor_layer is None:
        raise ValueError("Missing layer: tr_factor")

    factor = factor_layer.select(["rgn_id", "year", "factor"])

    # STEP 4: Join tourism and sustainability (full outer)
    tr_data = tourism.join(sustain, on=["rgn_id", "year"], how="full")

    # Fill missing s_score with 0.5
    tr_data = tr_data.with_columns(pl.col("s_score").fill_null(0.5))

    # STEP 5: Calculate Xtr
    tr_model = tr_data.with_columns([(pl.col("ep") * pl.col("s_score")).alias("Xtr")]).select(
        ["rgn_id", "year", "Xtr"]
    )

    # STEP 6: Join with factor (inner join)
    tr_modelnew = tr_model.join(factor, on=["rgn_id", "year"], how="inner")

    # Apply correction factor
    tr_modelnew = tr_modelnew.with_columns((pl.col("Xtr") * pl.col("factor")).alias("xtr"))

    # Remove null xtr
    tr_modelnew = tr_modelnew.filter(pl.col("xtr").is_not_null())

    # STEP 7: Calculate reference points per year
    # 90th percentile (p_max) and 0th percentile (p_min)
    p_ref_stats = tr_modelnew.group_by("year").agg(
        [
            pl.col("xtr").quantile(0.9).alias("p_max"),
            pl.col("xtr").min().alias("p_min"),  # 0th percentile = min
        ]
    )

    # STEP 8: Join and calculate status
    tr_scores = tr_modelnew.join(p_ref_stats, on="year", how="left")
    tr_scores = tr_scores.with_columns(
        [
            ((pl.col("xtr") - pl.col("p_min")) / (pl.col("p_max") - pl.col("p_min")))
            .alias("status")
            .clip(upper_bound=1.0)
        ]
    )
    tr_scores = tr_scores.select(["rgn_id", "year", "status"])

    # STEP 9: Extract status for scenario year
    tr_status = (
        tr_scores.filter(pl.col("year") == scen_year)
        .with_columns(
            [(pl.col("status") * 100).alias("score"), pl.lit("status").alias("dimension")]
        )
        .rename({"rgn_id": "region_id"})
        .select(["region_id", "score", "dimension"])
    )

    # STEP 10: Calculate trend
    tr_trend = calculate_trend(status_data=tr_scores, trend_years=trend_years, default_trend=None)

    return tr_status, tr_trend
