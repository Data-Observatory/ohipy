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


def _ensure_pandas(df):
    """Convert polars DataFrame to pandas if needed, pass through pandas unchanged."""
    if df is None:
        return None
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    return df


def TR(layers):
    """
    Calculate TR (Tourism & Recreation) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    # Import here to avoid circular imports
    from ohipy.calculate import calculate_trend

    # Get scenario year
    scen_year = layers["data"].get("scenario_year", 2024)
    trend_years = list(range(scen_year - 4, scen_year + 1))

    # STEP 1: Load tourism jobs percentage
    tourism_layer = _ensure_pandas(layers["data"].get("tr_jobs_pct_tourism"))
    if tourism_layer is None:
        raise ValueError("Missing layer: tr_jobs_pct_tourism")

    tourism = tourism_layer.copy()
    # Columns: rgn_id, year, ep
    tourism = tourism[["rgn_id", "year", "ep"]]

    # STEP 2: Load sustainability scores
    sustain_layer = _ensure_pandas(layers["data"].get("tr_sustainability"))
    if sustain_layer is None:
        raise ValueError("Missing layer: tr_sustainability")

    sustain = sustain_layer.copy()
    # Columns: rgn_id, year, s_score
    sustain = sustain[["rgn_id", "year", "s_score"]]

    # STEP 3: Load correction factor
    factor_layer = _ensure_pandas(layers["data"].get("tr_factor"))
    if factor_layer is None:
        raise ValueError("Missing layer: tr_factor")

    factor = factor_layer.copy()
    # Columns: rgn_id, year, factor
    factor = factor[["rgn_id", "year", "factor"]]

    # STEP 4: Join tourism and sustainability
    tr_data = tourism.merge(sustain, on=["rgn_id", "year"], how="outer")

    # Fill missing s_score with 0.5
    tr_data["s_score"] = tr_data["s_score"].fillna(0.5)

    # STEP 5: Calculate Xtr
    tr_model = tr_data.copy()
    tr_model["E"] = tr_model["ep"]
    tr_model["S"] = tr_model["s_score"]
    tr_model["Xtr"] = tr_model["E"] * tr_model["S"]
    tr_model = tr_model[["rgn_id", "year", "Xtr"]]

    # STEP 6: Merge with factor
    tr_modelnew = tr_model.merge(factor, on=["rgn_id", "year"], how="inner")

    # Apply correction factor
    tr_modelnew["xtr"] = tr_modelnew["Xtr"] * tr_modelnew["factor"]

    # Remove NA xtr
    tr_modelnew = tr_modelnew[~tr_modelnew["xtr"].isna()]

    # STEP 7: Calculate reference points per year
    # 90th percentile (p_max) and 0th percentile (p_min)
    p_ref_stats = (
        tr_modelnew.groupby("year")["xtr"]
        .agg([("p_max", lambda x: x.quantile(0.9)), ("p_min", lambda x: x.quantile(0.0))])
        .reset_index()
    )

    # STEP 8: Merge and calculate status
    tr_scores = tr_modelnew.merge(p_ref_stats, on="year", how="left")
    tr_scores["status"] = (tr_scores["xtr"] - tr_scores["p_min"]) / (
        tr_scores["p_max"] - tr_scores["p_min"]
    )
    tr_scores["status"] = tr_scores["status"].apply(lambda x: min(x, 1.0))
    tr_scores = tr_scores[["rgn_id", "year", "status"]]

    # STEP 9: Extract status for scenario year
    tr_status = tr_scores[tr_scores["year"] == scen_year].copy()
    tr_status["score"] = tr_status["status"] * 100
    tr_status = tr_status.rename(columns={"rgn_id": "region_id"})
    tr_status["dimension"] = "status"
    tr_status = tr_status[["region_id", "score", "dimension"]]

    # STEP 10: Calculate trend
    tr_trend = calculate_trend(status_data=tr_scores, trend_years=trend_years, default_trend=None)

    return tr_status, tr_trend
