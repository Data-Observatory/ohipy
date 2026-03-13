"""LSP Goal - Lasting Special Places

Calculates status and trend for the Lasting Special Places goal.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 1018-1062):
1. Set reference percentages: ref_pct_cmpa = 40, ref_pct_cp = 40
2. Load offshore (lsp_area_offshore3mn) and inland (lsp_area_inland1mn) protected areas
3. Full join on region_id and year
4. Status: (min(cmpa/40, 1) + min(cp/40, 1)) / 2 × 100
5. Trend: Calculate using calculate_trend() on last 5 years
"""

import pandas as pd
import numpy as np
from ..calculate import calculate_trend


def _ensure_pandas(df):
    """Convert polars DataFrame to pandas if needed, pass through pandas unchanged."""
    if df is None:
        return None
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    return df


def LSP(layers):
    """
    Calculate LSP (Lasting Special Places) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    scenario_year = layers["data"]["scenario_year"]

    # Reference percentages
    ref_pct_cmpa = 40
    ref_pct_cp = 40

    # STEP 1: Load offshore protected area layer
    offshore_layer = _ensure_pandas(layers["data"].get("lsp_area_offshore3mn"))
    if offshore_layer is None:
        raise ValueError("Missing layer: lsp_area_offshore3mn")

    offshore = offshore_layer.copy()
    offshore = offshore.rename(columns={"rgn_id": "region_id", "value_3": "cmpa"})
    offshore = offshore[["region_id", "year", "cmpa"]]

    # STEP 2: Load inland protected area layer
    inland_layer = _ensure_pandas(layers["data"].get("lsp_area_inland1mn"))
    if inland_layer is None:
        raise ValueError("Missing layer: lsp_area_inland1mn")

    inland = inland_layer.copy()
    inland = inland.rename(columns={"rgn_id": "region_id", "value_1": "cp"})
    inland = inland[["region_id", "year", "cp"]]

    # STEP 3: Full join on region_id and year
    lsp_data = offshore.merge(inland, on=["region_id", "year"], how="outer")

    # STEP 4: Calculate status
    lsp_data["status"] = (
        (lsp_data["cmpa"] / ref_pct_cp).clip(upper=1).fillna(0)
        + (lsp_data["cp"] / ref_pct_cmpa).clip(upper=1).fillna(0)
    ) / 2

    # Filter out NaN status
    status_data = lsp_data[~lsp_data["status"].isna()].copy()

    # STEP 5: Get status for scenario year
    r_status = status_data[status_data["year"] == scenario_year].copy()
    r_status["score"] = r_status["status"] * 100
    r_status = r_status.rename(columns={"region_id": "region_id"})
    r_status["dimension"] = "status"
    r_status = r_status[["region_id", "score", "dimension"]]

    # STEP 6: Calculate trend
    trend_years = list(range(scenario_year - 4, scenario_year + 1))

    # Use calculate_trend on status_data (expects columns: region_id, year, status)
    r_trend = calculate_trend(status_data=status_data, trend_years=trend_years)

    return r_status, r_trend
