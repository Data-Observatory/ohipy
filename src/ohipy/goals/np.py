"""NP Goal - Natural Products

Calculates status and trend for the Natural Products goal based on harvest data.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 329-433):
1. Load harvest tonnes, relative tonnes, weights, and sustainability coefficients
2. Merge all data layers
3. Calculate product scores: Pc = tonnes_rel × coef
4. Calculate weighted mean status per region-year
5. Extract status for scenario year
6. Calculate trend using linear regression
"""

from __future__ import annotations

from typing import cast

import polars as pl


def NP(layers: dict[str, object]) -> tuple[pl.DataFrame, pl.DataFrame]:  # noqa: N802
    """
    Calculate NP (Natural Products) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a polars DataFrame with columns:
               [region_id, score, dimension]
    """
    # Import here to avoid circular imports
    from ohipy.calculate import calculate_trend

    # Get scenario year
    data_layers = cast(dict[str, object], layers["data"])
    scen_year = cast(int, data_layers.get("scenario_year", 2024))
    trend_years = list(range(scen_year - 4, scen_year + 1))

    # STEP 1: Load harvest tonnes
    h_tonnes_layer = cast(pl.DataFrame | None, data_layers.get("np_harvest_tonnes"))
    if h_tonnes_layer is None:
        raise ValueError("Missing layer: np_harvest_tonnes")

    h_tonnes = (
        h_tonnes_layer.clone()
        .rename({"producto": "Producto"})
        .with_columns(pl.col("rgn_id").cast(pl.Float64))
        .select(["year", "rgn_id", "Producto", "tonnes"])
    )

    # STEP 2: Load harvest tonnes relative
    h_tonnes_rel_layer = cast(pl.DataFrame | None, data_layers.get("np_harvest_tonnes_relative"))
    if h_tonnes_rel_layer is None:
        raise ValueError("Missing layer: np_harvest_tonnes_relative")

    h_tonnes_rel = (
        h_tonnes_rel_layer.clone()
        .rename({"producto": "Producto"})
        .with_columns(pl.col("rgn_id").cast(pl.Float64))
        .select(["year", "rgn_id", "Producto", "tonnes_rel"])
    )

    # STEP 3: Load harvest tonnes weight
    h_tonnes_w_layer = cast(pl.DataFrame | None, data_layers.get("np_harvest_tonnes_weigth"))
    if h_tonnes_w_layer is None:
        raise ValueError("Missing layer: np_harvest_tonnes_weigth")

    h_tonnes_w = (
        h_tonnes_w_layer.clone()
        .rename({"producto": "Producto", "weight": "proportion"})
        .with_columns(pl.col("rgn_id").cast(pl.Float64))
        .select(["year", "rgn_id", "Producto", "proportion"])
    )

    # STEP 4: Load FOFM sustainability scores
    np_fofm_layer = cast(pl.DataFrame | None, data_layers.get("np_fofm_scores"))
    if np_fofm_layer is None:
        raise ValueError("Missing layer: np_fofm_scores")

    np_fofm = (
        np_fofm_layer.clone()
        .rename({"producto": "Producto", "score": "coef"})
        .with_columns(pl.col("rgn_id").cast(pl.Float64))
        .select(["year", "rgn_id", "Producto", "coef"])
    )

    # STEP 5: Load seaweed sustainability scores
    np_seaweed_layer = cast(pl.DataFrame | None, data_layers.get("np_seaweed_sust"))
    if np_seaweed_layer is None:
        raise ValueError("Missing layer: np_seaweed_sust")

    np_seaweed = (
        np_seaweed_layer.clone()
        .rename({"producto": "Producto", "score": "coef"})
        .with_columns(pl.col("rgn_id").cast(pl.Float64))
        .select(["year", "rgn_id", "Producto", "coef"])
    )

    # STEP 6: Merge harvest data
    np_harvest = (
        h_tonnes_w.join(h_tonnes, on=["year", "rgn_id", "Producto"], how="full")
        .with_columns(
            pl.coalesce(["year", "year_right"]).alias("year"),
            pl.coalesce(["rgn_id", "rgn_id_right"]).alias("rgn_id"),
            pl.coalesce(["Producto", "Producto_right"]).alias("Producto"),
        )
        .drop(["year_right", "rgn_id_right", "Producto_right"])
    )

    np_harvest = (
        np_harvest.join(h_tonnes_rel, on=["year", "rgn_id", "Producto"], how="full")
        .with_columns(
            pl.coalesce(["year", "year_right"]).alias("year"),
            pl.coalesce(["rgn_id", "rgn_id_right"]).alias("rgn_id"),
            pl.coalesce(["Producto", "Producto_right"]).alias("Producto"),
        )
        .drop(["year_right", "rgn_id_right", "Producto_right"])
    )

    # STEP 7: Combine sustainability scores
    np_sust = pl.concat([np_fofm, np_seaweed])

    # STEP 8: Merge harvest with sustainability
    np_harvest = (
        np_harvest.join(np_sust, on=["year", "rgn_id", "Producto"], how="full")
        .with_columns(
            pl.coalesce(["year", "year_right"]).alias("year"),
            pl.coalesce(["rgn_id", "rgn_id_right"]).alias("rgn_id"),
            pl.coalesce(["Producto", "Producto_right"]).alias("Producto"),
        )
        .drop(["year_right", "rgn_id_right", "Producto_right"])
    )

    # STEP 9: Calculate product scores
    np_status_all = np_harvest.with_columns((pl.col("tonnes_rel") * pl.col("coef")).alias("Pc"))

    # STEP 10: Filter to last 5 years and non-NA tonnes
    np_status_all = np_status_all.filter(
        pl.col("tonnes").is_not_null() & pl.col("year").is_in(trend_years)
    )

    # STEP 11: Fill missing proportions with 1
    np_status_all = np_status_all.with_columns(pl.col("proportion").fill_null(1))

    # STEP 12: Calculate weighted mean status per region-year
    np_status_all = np_status_all.group_by(["rgn_id", "year"]).agg(
        ((pl.col("Pc") * pl.col("proportion")).mean() * 100).alias("status")
    )

    # Remove NA status
    np_status_all = np_status_all.filter(pl.col("status").is_not_null())

    # STEP 13: Extract status for scenario year
    np_status_current = (
        np_status_all.filter(pl.col("year") == scen_year)
        .with_columns(
            [
                pl.lit("status").alias("dimension"),
                pl.col("status").round(4).alias("score"),
            ]
        )
        .rename({"rgn_id": "region_id"})
        .select(["region_id", "dimension", "score"])
    )

    # STEP 14: Calculate trend
    np_trend = calculate_trend(
        status_data=np_status_all, trend_years=trend_years, default_trend=None
    )

    return np_status_current, np_trend
