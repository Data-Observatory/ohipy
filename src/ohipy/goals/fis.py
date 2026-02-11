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

import numpy as np
import pandas as pd


def FIS(layers):
    """
    Calculate FIS (Fisheries) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    # Import here to avoid circular imports
    from ohipy.calculate import calculate_trend

    # Get scenario year from layers data
    scen_year = layers["data"].get("scenario_year", 2024)

    # Define trend years (last 5 years including scenario year)
    trend_years = list(range(scen_year - 4, scen_year + 1))

    # STEP 0: Load catch data
    # SelectLayersData equivalent for fis_meancatch
    catch_layer = layers["data"].get("fis_meancatch")
    if catch_layer is None:
        raise ValueError("Missing layer: fis_meancatch")

    c = catch_layer.copy()
    # Standardize column names
    c = c.rename(columns={"rgn_id": "rgn_id", "Spp": "Spp", "year": "year", "catch": "catch"})

    # Filter to trend years
    c = c[c["year"].isin(trend_years)]
    c = c[["rgn_id", "Spp", "year", "catch"]]

    # STEP 0b: Load B/Bmsy data
    bbmsy_layer = layers["data"].get("fis_b_bmsy")
    if bbmsy_layer is None:
        raise ValueError("Missing layer: fis_b_bmsy")

    b = bbmsy_layer.copy()
    # Standardize column names (note: Especie → Spp)
    b = b.rename(
        columns={
            "rgn_id": "rgn_id",
            "year": "year",
            "Especie": "Spp",
            "val_num": "b_bmsy",
        }
    )

    # Filter to trend years and remove NAs
    b = b[b["year"].isin(trend_years)]
    b = b.dropna(subset=["b_bmsy", "rgn_id"])
    b = b[["rgn_id", "year", "Spp", "b_bmsy"]]

    # STEP 1: Score B/Bmsy with buffer logic
    alpha = 0.5
    beta = 0.25
    lower_buffer = 0.95
    upper_buffer = 1.05

    def score_bbmsy(b_bmsy_val):
        """Apply buffer scoring to B/Bmsy values."""
        if b_bmsy_val < lower_buffer:
            return b_bmsy_val
        elif lower_buffer <= b_bmsy_val <= upper_buffer:
            return 1.0
        else:
            # Underfishing penalty
            score = 1 - alpha * (b_bmsy_val - upper_buffer)
            return max(score, beta)  # Floor at beta (0.25)

    b["score"] = b["b_bmsy"].apply(score_bbmsy)

    # STEP 2: Merge catch and B/Bmsy data
    data_fis = c.merge(
        b[["rgn_id", "Spp", "year", "b_bmsy", "score"]],
        on=["rgn_id", "Spp", "year"],
        how="left",
    )

    # DEBUG: Check data_fis columns
    # print(f"DEBUG: data_fis columns: {data_fis.columns.tolist()}")

    # STEP 3: Fill missing scores
    # Following R code exactly (lines 78-94):
    # Calculate regional mean score per region/year
    data_fis_gf = (
        data_fis.groupby(["rgn_id", "year"])
        .apply(lambda x: x.assign(mean_score=x["score"].mean()))
        .reset_index()
    )

    # DEBUG: Check data_fis_gf columns
    # print(f"DEBUG: data_fis_gf columns: {data_fis_gf.columns.tolist()}")

    # Calculate global mean score per year (across all regions)
    global_means = data_fis.groupby("year")["score"].mean().reset_index()
    global_means = global_means.rename(columns={"score": "mean_score_global"})

    # DEBUG: Check global_means columns
    # print(f"DEBUG: global_means columns: {global_means.columns.tolist()}")

    data_fis_gf2 = data_fis_gf.merge(global_means, on="year", how="left")

    # Fill missing scores: use score if available, else use global mean
    # (R code line 91: ifelse(!is.na(score), score, mean_score_global))
    data_fis_gf2["mean_score"] = data_fis_gf2.apply(
        lambda row: row["score"] if pd.notna(row["score"]) else row["mean_score_global"],
        axis=1,
    )

    data_fis_gf3 = data_fis_gf2.copy()

    # STEP 3.1: Count species diversity per region/year
    sp = c.groupby(["rgn_id", "year"])["Spp"].nunique().reset_index()
    sp = sp.rename(columns={"Spp": "n"})

    # STEP 4: Select columns and merge with species count
    status_data = data_fis_gf3[["rgn_id", "Spp", "year", "catch", "mean_score"]].copy()

    # Calculate catch weights
    sum_catch = status_data.groupby(["year", "rgn_id"])["catch"].sum().reset_index()
    sum_catch = sum_catch.rename(columns={"catch": "SumCatch"})
    status_data = status_data.merge(sum_catch, on=["year", "rgn_id"], how="left")
    status_data["wprop"] = status_data["catch"] / status_data["SumCatch"]

    # Merge with species count
    status_data = status_data.merge(sp, on=["rgn_id", "year"], how="left")

    # Ensure mean_score is numeric
    status_data["mean_score"] = pd.to_numeric(status_data["mean_score"], errors="coerce")

    # STEP 5: Apply cascading species diversity penalty
    # If n == 3: reduce score by 30% (multiply by 0.7)
    status_data["mean_score_f1"] = status_data.apply(
        lambda row: (
            row["mean_score"] - 0.3 * row["mean_score"] if row["n"] == 3 else row["mean_score"]
        ),
        axis=1,
    )

    # If n == 2: reduce f1 score by 40%
    status_data["mean_score_f2"] = status_data.apply(
        lambda row: (
            row["mean_score_f1"] - 0.4 * row["mean_score_f1"]
            if row["n"] == 2
            else row["mean_score_f1"]
        ),
        axis=1,
    )

    # If n == 1: reduce f2 score by 50%
    status_data["mean_score_final"] = status_data.apply(
        lambda row: (
            row["mean_score_f2"] - 0.5 * row["mean_score_f2"]
            if row["n"] == 1
            else row["mean_score_f2"]
        ),
        axis=1,
    )

    # STEP 6: Calculate weighted geometric mean per region/year
    # Formula: ∏(score^wprop) = exp(∑(wprop * log(score)))
    # Handle zeros and negatives carefully
    status_data["log_score"] = status_data["mean_score_final"].apply(
        lambda x: np.log(x) if x > 0 else np.nan
    )
    status_data["weighted_log"] = status_data["wprop"] * status_data["log_score"]

    status_data_final = (
        status_data.groupby(["rgn_id", "year"])
        .agg(status=("weighted_log", lambda x: np.exp(np.nansum(x))))
        .reset_index()
    )

    # STEP 7: Extract status for scenario year
    status_df = status_data_final[status_data_final["year"] == scen_year].copy()
    status_df["score"] = status_df["status"] * 100
    status_df["dimension"] = "status"
    status_df = status_df[["rgn_id", "score", "dimension"]]
    status_df = status_df.rename(columns={"rgn_id": "region_id"})

    # STEP 8: Calculate trend
    trend_df = calculate_trend(
        status_data=status_data_final, trend_years=trend_years, default_trend=None
    )

    return status_df, trend_df
