"""LSP Goal - Lasting Special Places

Calculates status and trend for the Lasting Special Places goal.
Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 1018-1062):
1. Set reference percentages: ref_pct_cmpa = 40, ref_pct_cp = 40
2. Load offshore (lsp_area_offshore3mn) and inland (lsp_area_inland1mn) protected areas
3. Full join on region_id and year
4. Status: (min(cmpa/40, 1) + min(cp/40, 1)) / 2 × 100
5. Trend: Calculate using calculate_trend() on last 5 years
"""

import polars as pl

from ..calculate import calculate_trend


def LSP(layers):
    scenario_year = layers["data"]["scenario_year"]

    ref_pct_cmpa = 40
    ref_pct_cp = 40

    offshore_layer = layers["data"].get("lsp_area_offshore3mn")
    if offshore_layer is None:
        raise ValueError("Missing layer: lsp_area_offshore3mn")

    offshore = offshore_layer.clone()
    offshore = offshore.rename({"rgn_id": "region_id", "value_3": "cmpa"})
    offshore = offshore.select(["region_id", "year", "cmpa"])

    inland_layer = layers["data"].get("lsp_area_inland1mn")
    if inland_layer is None:
        raise ValueError("Missing layer: lsp_area_inland1mn")

    inland = inland_layer.clone()
    inland = inland.rename({"rgn_id": "region_id", "value_1": "cp"})
    inland = inland.select(["region_id", "year", "cp"])

    lsp_data = offshore.join(inland, on=["region_id", "year"], how="full")

    lsp_data = lsp_data.with_columns(
        (
            (
                (pl.col("cmpa") / ref_pct_cmpa).clip(upper_bound=1).fill_null(0)
                + (pl.col("cp") / ref_pct_cp).clip(upper_bound=1).fill_null(0)
            )
            / 2
        ).alias("status")
    )

    status_data = lsp_data.filter(pl.col("status").is_not_null())

    r_status = status_data.filter(pl.col("year") == scenario_year).clone()
    r_status = r_status.with_columns(
        [(pl.col("status") * 100).alias("score"), pl.lit("status").alias("dimension")]
    )
    r_status = r_status.select(["region_id", "score", "dimension"])

    trend_years = list(range(scenario_year - 4, scenario_year + 1))
    r_trend = calculate_trend(status_data=status_data, trend_years=trend_years)

    return r_status, r_trend
