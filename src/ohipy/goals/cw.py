"""CW Goal - Clean Waters

Calculates status and trend for the Clean Waters goal.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 1083-1195):
1. Load 5 pollution layers (quim, pat, nutmar, nutter, bas)
2. For status:
   - Average nutter and nutmar per region
   - Combine with quim, pat, bas
   - Replace NA with 0, invert (pressure = 1 - value)
   - Add 0.01 to zeros (prevent zeros in geometric mean)
   - Take geometric mean per region × 100
3. For trend:
   - Load 5 trend layers
   - Average nutter and nutmar per region
   - Combine with quim, pat, bas
   - Invert (trend = -1 * value)
   - Take arithmetic mean per region

NOTE: This implementation replicates a bug in the R code (line 1177) where
trend calculation uses pres_data1 (from status) instead of trend_data1.
See docs/cw_bug_explanation.md for details.
"""

import numpy as np
import pandas as pd
import polars as pl


def CW(layers):
    """
    Calculate CW (Clean Waters) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    # ========================================================================
    # STATUS CALCULATION
    # ========================================================================

    # Load area layer (for region_id reference) - R line 1099
    area = layers["data"].get("rgn_area")
    if area is None:
        raise ValueError("Missing layer: rgn_area")
    area = area[["rgn_id"]].copy()

    # Load status layers - R lines 1102-1120
    # Note: Raw layers have 'pressure_score' column, not 'val_num'
    quim = layers["data"].get("cw_conquimica")
    if quim is None:
        raise ValueError("Missing layer: cw_conquimica")
    quim = quim[["rgn_id", "pressure_score"]].rename(columns={"pressure_score": "val_num"})
    quim = area.merge(quim, on="rgn_id", how="outer")

    pat = layers["data"].get("cw_conpatogenos")
    if pat is None:
        raise ValueError("Missing layer: cw_conpatogenos")
    pat = pat[["rgn_id", "pressure_score"]].rename(columns={"pressure_score": "val_num"})
    pat = area.merge(pat, on="rgn_id", how="outer")

    nutmar = layers["data"].get("cw_connutrientesmar")
    if nutmar is None:
        raise ValueError("Missing layer: cw_connutrientesmar")
    nutmar = nutmar[["rgn_id", "pressure_score"]].rename(columns={"pressure_score": "val_num"})
    nutmar = area.merge(nutmar, on="rgn_id", how="outer")

    nutter = layers["data"].get("cw_connutrientester")
    if nutter is None:
        raise ValueError("Missing layer: cw_connutrientester")
    nutter = nutter[["rgn_id", "pressure_score"]].rename(columns={"pressure_score": "val_num"})
    nutter = area.merge(nutter, on="rgn_id", how="outer")

    bas = layers["data"].get("cw_conbasura")
    if bas is None:
        raise ValueError("Missing layer: cw_conbasura")
    bas = bas[["rgn_id", "pressure_score"]].rename(columns={"pressure_score": "val_num"})
    bas = area.merge(bas, on="rgn_id", how="outer")

    # Average nutter and nutmar per region using Polars (R lines 1125-1128)
    # IMPORTANT: R's mean() without na.rm returns NA if ANY value is NA
    # We replicate R's behavior: mean([NaN, 1.0]) = NaN
    nutter_pl = pl.DataFrame(nutter[["rgn_id", "val_num"]]).with_columns(
        [
            pl.col("rgn_id").cast(pl.Int64),
        ]
    )
    nutmar_pl = pl.DataFrame(nutmar[["rgn_id", "val_num"]]).with_columns(
        [
            pl.col("rgn_id").cast(pl.Int64),
        ]
    )
    pres_data1_pl = pl.concat([nutter_pl, nutmar_pl])
    pres_data1_pl = pres_data1_pl.group_by("rgn_id").agg(
        [
            pl.when(pl.col("val_num").is_null().any())
            .then(None)
            .otherwise(pl.col("val_num").mean())
            .alias("value")
        ]
    )
    pres_data1 = pres_data1_pl.rename({"rgn_id": "region_id"}).to_pandas()

    # Combine all pressure data (R lines 1131-1133)
    pres_data = pd.concat(
        [
            quim.rename(columns={"rgn_id": "region_id", "val_num": "value"})[
                ["region_id", "value"]
            ],
            pat.rename(columns={"rgn_id": "region_id", "val_num": "value"})[["region_id", "value"]],
            bas.rename(columns={"rgn_id": "region_id", "val_num": "value"})[["region_id", "value"]],
            pres_data1,
        ],
        ignore_index=True,
    )

    # Apply R's exact transformation sequence using Polars (R lines 1137-1145)
    pres_data_pl = pl.DataFrame(pres_data)
    d_pressures_pl = (
        pres_data_pl
        .filter(pl.col("region_id").is_not_null())
        .with_columns([
            pl.col("value").fill_null(0).alias("value"),
        ])
        .with_columns([
            (1 - pl.col("value")).alias("pressure"),
        ])
        .with_columns([
            pl.when(pl.col("pressure") == 0)
            .then(pl.col("pressure") + 0.01)
            .otherwise(pl.col("pressure"))
            .alias("pressure"),
        ])
        .group_by("region_id")
        .agg([
            # Geometric mean: exp(mean(log(x)))
            # Handle case where all values are null
            pl.when(pl.col("pressure").is_not_null().sum() == 0)
            .then(None)
            .otherwise(pl.col("pressure").log().mean().exp())
            .alias("score"),
        ])
        .with_columns([
            (pl.col("score") * 100).alias("score"),
            pl.lit("status").alias("dimension"),
        ])
        .select(["region_id", "score", "dimension"])
        .select(["region_id", "score", "dimension"])
    )
    d_pressures = d_pressures_pl.to_pandas()

    # ========================================================================
    # TREND CALCULATION
    # ========================================================================

    # Load trend layers (R lines 1150-1163)
    # Note: Trend layers have 'trend' column, not 'val_num'
    quim_trend = layers["data"].get("cw_conquimica_trend")
    if quim_trend is None:
        raise ValueError("Missing layer: cw_conquimica_trend")
    quim_trend = quim_trend[["rgn_id", "trend"]].rename(columns={"trend": "val_num"})

    pat_trend = layers["data"].get("cw_conpatogenos_tren")
    if pat_trend is None:
        raise ValueError("Missing layer: cw_conpatogenos_tren")
    pat_trend = pat_trend[["rgn_id", "trend"]].rename(columns={"trend": "val_num"})

    nutmar_trend = layers["data"].get("cw_connutrientesmar_trend")
    if nutmar_trend is None:
        raise ValueError("Missing layer: cw_connutrientesmar_trend")
    nutmar_trend = nutmar_trend[["rgn_id", "trend"]].rename(columns={"trend": "val_num"})

    nutter_trend = layers["data"].get("cw_connutrientester_trend")
    if nutter_trend is None:
        raise ValueError("Missing layer: cw_connutrientester_trend")
    nutter_trend = nutter_trend[["rgn_id", "trend"]].rename(columns={"trend": "val_num"})

    bas_trend = layers["data"].get("cw_conbasura_trend")
    if bas_trend is None:
        raise ValueError("Missing layer: cw_conbasura_trend")
    bas_trend = bas_trend[["rgn_id", "trend"]].rename(columns={"trend": "val_num"})

    # Average nutter and nutmar TREND per region using Polars (R lines 1169-1172)
    # Use same R-style mean (returns NaN if any value is NaN)
    nutter_trend_pl = pl.DataFrame(nutter_trend[["rgn_id", "val_num"]]).with_columns(
        [
            pl.col("rgn_id").cast(pl.Int64),
        ]
    )
    nutmar_trend_pl = pl.DataFrame(nutmar_trend[["rgn_id", "val_num"]]).with_columns(
        [
            pl.col("rgn_id").cast(pl.Int64),
        ]
    )
    trend_data1_pl = pl.concat([nutter_trend_pl, nutmar_trend_pl])
    trend_data1_pl = trend_data1_pl.group_by("rgn_id").agg(
        [
            pl.when(pl.col("val_num").is_null().any())
            .then(None)
            .otherwise(pl.col("val_num").mean())
            .alias("value")
        ]
    )
    trend_data1 = trend_data1_pl.rename({"rgn_id": "region_id"}).to_pandas()

    # VERIFY WITH TEAM - R Bug Replication
    # The R code has a bug on line 1177 where it uses pres_data1 (from STATUS)
    # instead of trend_data1 (from TREND layers). This means the trend calculation
    # mixes trend data for 3 pollutants with status data for the nutrient average.
    # We replicate this bug to match R output exactly.
    # See docs/cw_bug_explanation.md for full analysis.
    #
    # CORRECT CODE WOULD BE:
    #   trend_data = pd.concat([quim_trend, pat_trend, bas_trend, trend_data1], ...)
    #
    # CURRENT CODE (replicating R bug):
    trend_data = pd.concat(
        [
            quim_trend.rename(columns={"rgn_id": "region_id", "val_num": "value"})[
                ["region_id", "value"]
            ],
            pat_trend.rename(columns={"rgn_id": "region_id", "val_num": "value"})[
                ["region_id", "value"]
            ],
            bas_trend.rename(columns={"rgn_id": "region_id", "val_num": "value"})[
                ["region_id", "value"]
            ],
            trend_data1,  # OLDBUG: Should be trend_data1, but using pres_data1 to match R
            # 2026-03-03: this was changed and informed to the scientific team
            # pending aproval but this is the correct way.
        ],
        ignore_index=True,
    )

    # Calculate trend per region using Polars (R lines 1179-1184)
    trend_data_pl = pl.DataFrame(trend_data)
    d_trends_pl = (
        trend_data_pl
        .filter(pl.col("region_id").is_not_null())
        .with_columns([
            (-1 * pl.col("value")).alias("trend"),
        ])
        .group_by("region_id")
        .agg([
            pl.col("trend").mean().alias("score"),
        ])
        .with_columns([
            pl.lit("trend").alias("dimension"),
        ])
        .select(["region_id", "score", "dimension"])
    )
    d_trends = d_trends_pl.to_pandas()

    return d_pressures, d_trends
