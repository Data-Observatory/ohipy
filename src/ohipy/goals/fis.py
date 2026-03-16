"""FIS Goal - Fisheries

Calculates status and trend for the Fisheries goal based on catch data and B/Bmsy ratios.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 17-180):
1. Load catch data (fis_meancatch) and B/Bmsy data (fis_b_bmsy) for last 5 years
2. Score B/Bmsy with buffer: < 0.95 → score=b_bmsy, 0.95-1.05 → score=1.0, > 1.05 → penalize
3. Fill missing scores with regional mean, then global mean
4. Apply species diversity penalty (fewer species → lower score)
5. Calculate weighted geometric mean by catch proportion
6. Calculate trend using linear regression
"""

import polars as pl


def FIS(layers):
    """
    Calculate FIS (Fisheries) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a polars DataFrame with columns:
               [region_id, score, dimension]
    """
    # Import here to avoid circular imports
    from ohipy.calculate import calculate_trend

    # Get scenario year from layers data
    scen_year = layers["data"].get("scenario_year", 2024)

    # Define trend years (last 5 years including scenario year)
    trend_years = list(range(scen_year - 4, scen_year + 1))

    # STEP 0: Load catch data
    catch_layer = layers["data"].get("fis_meancatch")
    if catch_layer is None:
        raise ValueError("Missing layer: fis_meancatch")

    c = catch_layer.clone()

    # Select needed columns and filter to trend years
    c = c.select(["rgn_id", "Spp", "year", "catch"])
    c = c.filter(pl.col("year").is_in(trend_years))

    # STEP 0b: Load B/Bmsy data
    bbmsy_layer = layers["data"].get("fis_b_bmsy")
    if bbmsy_layer is None:
        raise ValueError("Missing layer: fis_b_bmsy")

    b = bbmsy_layer.clone()

    # Standardize column names (note: Especie → Spp)
    b = b.rename({"Especie": "Spp"})
    b = b.select(["rgn_id", "year", "Spp", "b_bmsy"])

    # Filter to trend years and remove nulls
    b = b.filter(pl.col("year").is_in(trend_years))
    b = b.drop_nulls(subset=["b_bmsy", "rgn_id"])

    # STEP 1: Score B/Bmsy with buffer logic
    alpha = 0.5
    beta = 0.25
    lower_buffer = 0.95
    upper_buffer = 1.05

    # Vectorized B/Bmsy scoring with buffer logic using polars when/then/otherwise
    b = b.with_columns(
        pl.when(pl.col("b_bmsy") < lower_buffer)
        .then(pl.col("b_bmsy"))
        .when((pl.col("b_bmsy") >= lower_buffer) & (pl.col("b_bmsy") <= upper_buffer))
        .then(1.0)
        .otherwise((1 - alpha * (pl.col("b_bmsy") - upper_buffer)).clip(lower_bound=beta))
        .alias("score")
    )

    # STEP 2: Join catch and B/Bmsy data
    data_fis = c.join(
        b.select(["rgn_id", "Spp", "year", "b_bmsy", "score"]),
        on=["rgn_id", "Spp", "year"],
        how="left",
    )

    # STEP 3: Fill missing scores
    # Following R code exactly (lines 78-94):
    # Calculate regional mean score per region/year and global mean per year

    # Calculate regional mean score per region/year
    data_fis_gf = data_fis.with_columns(
        pl.col("score").mean().over(["rgn_id", "year"]).alias("mean_score")
    )

    # Calculate global mean score per year (across all regions)
    global_means = data_fis.group_by("year").agg(pl.col("score").mean().alias("mean_score_global"))

    # Join with global means
    data_fis_gf2 = data_fis_gf.join(global_means, on="year", how="left")

    # Fill missing scores: use score if available, else use global mean
    # (R code line 91: ifelse(!is.na(score), score, mean_score_global))
    data_fis_gf3 = data_fis_gf2.with_columns(
        pl.when(pl.col("score").is_not_null())
        .then(pl.col("score"))
        .otherwise(pl.col("mean_score_global"))
        .alias("mean_score")
    )

    # STEP 3.1: Count species diversity per region/year
    sp = c.group_by(["rgn_id", "year"]).agg(pl.col("Spp").n_unique().alias("n"))

    # STEP 4: Select columns and merge with species count
    status_data = data_fis_gf3.select(["rgn_id", "Spp", "year", "catch", "mean_score"])

    # Calculate catch weights
    sum_catch = status_data.group_by(["year", "rgn_id"]).agg(
        pl.col("catch").sum().alias("SumCatch")
    )
    status_data = status_data.join(sum_catch, on=["year", "rgn_id"], how="left")
    status_data = status_data.with_columns((pl.col("catch") / pl.col("SumCatch")).alias("wprop"))

    # Merge with species count
    status_data = status_data.join(sp, on=["rgn_id", "year"], how="left")

    # Ensure mean_score is float64 (polars handles this automatically but explicit cast for safety)
    status_data = status_data.with_columns(pl.col("mean_score").cast(pl.Float64))

    # STEP 5: Apply cascading species diversity penalty (vectorized)
    # If n == 3: reduce score by 30% (multiply by 0.7)
    # If n == 2: reduce f1 score by 40% (multiply by 0.6)
    # If n == 1: reduce f2 score by 50% (multiply by 0.5)
    status_data = status_data.with_columns(
        pl.when(pl.col("n") == 3)
        .then(pl.col("mean_score") * 0.7)
        .otherwise(pl.col("mean_score"))
        .alias("mean_score_f1")
    )

    status_data = status_data.with_columns(
        pl.when(pl.col("n") == 2)
        .then(pl.col("mean_score_f1") * 0.6)
        .otherwise(pl.col("mean_score_f1"))
        .alias("mean_score_f2")
    )

    status_data = status_data.with_columns(
        pl.when(pl.col("n") == 1)
        .then(pl.col("mean_score_f2") * 0.5)
        .otherwise(pl.col("mean_score_f2"))
        .alias("mean_score_final")
    )

    # STEP 6: Calculate weighted geometric mean per region/year
    # Formula: ∏(score^wprop) = exp(∑(wprop * log(score)))
    # Handle zeros and negatives carefully
    status_data = status_data.with_columns(
        pl.when(pl.col("mean_score_final") > 0)
        .then(pl.col("mean_score_final").log())
        .otherwise(None)  # null for non-positive values
        .alias("log_score")
    )

    status_data = status_data.with_columns(
        (pl.col("wprop") * pl.col("log_score")).alias("weighted_log")
    )

    # Aggregate: sum weighted_log and exp to get weighted geometric mean
    status_data_final = status_data.group_by(["rgn_id", "year"]).agg(
        pl.col("weighted_log").sum().exp().alias("status")
    )

    # STEP 7: Extract status for scenario year
    status_df = status_data_final.filter(pl.col("year") == scen_year).select(
        [
            pl.col("rgn_id").alias("region_id"),
            (pl.col("status") * 100).alias("score"),
            pl.lit("status").alias("dimension"),
        ]
    )

    # STEP 8: Calculate trend
    trend_df = calculate_trend(
        status_data=status_data_final, trend_years=trend_years, default_trend=None
    )

    return status_df, trend_df
