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

import pandas as pd
import numpy as np


def geometric_mean(x):
    """Calculate geometric mean, handling zeros and NAs."""
    x_clean = x[~pd.isna(x)]
    if len(x_clean) == 0:
        return np.nan
    return np.exp(np.mean(np.log(x_clean)))


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
    area = layers['data'].get('rgn_area')
    if area is None:
        raise ValueError("Missing layer: rgn_area")
    area = area[['rgn_id']].copy()

    # Load status layers - R lines 1102-1120
    # Note: Raw layers have 'pressure_score' column, not 'val_num'
    quim = layers['data'].get('cw_conquimica')
    if quim is None:
        raise ValueError("Missing layer: cw_conquimica")
    quim = quim[['rgn_id', 'pressure_score']].rename(columns={'pressure_score': 'val_num'})
    quim = area.merge(quim, on='rgn_id', how='outer')

    pat = layers['data'].get('cw_conpatogenos')
    if pat is None:
        raise ValueError("Missing layer: cw_conpatogenos")
    pat = pat[['rgn_id', 'pressure_score']].rename(columns={'pressure_score': 'val_num'})
    pat = area.merge(pat, on='rgn_id', how='outer')

    nutmar = layers['data'].get('cw_connutrientesmar')
    if nutmar is None:
        raise ValueError("Missing layer: cw_connutrientesmar")
    nutmar = nutmar[['rgn_id', 'pressure_score']].rename(columns={'pressure_score': 'val_num'})
    nutmar = area.merge(nutmar, on='rgn_id', how='outer')

    nutter = layers['data'].get('cw_connutrientester')
    if nutter is None:
        raise ValueError("Missing layer: cw_connutrientester")
    nutter = nutter[['rgn_id', 'pressure_score']].rename(columns={'pressure_score': 'val_num'})
    nutter = area.merge(nutter, on='rgn_id', how='outer')

    bas = layers['data'].get('cw_conbasura')
    if bas is None:
        raise ValueError("Missing layer: cw_conbasura")
    bas = bas[['rgn_id', 'pressure_score']].rename(columns={'pressure_score': 'val_num'})
    bas = area.merge(bas, on='rgn_id', how='outer')

    # Average nutter and nutmar per region (R lines 1125-1128)
    # IMPORTANT: R's mean() without na.rm returns NA if ANY value is NA
    # pandas .agg('mean') ignores NaN by default (like R's na.rm=TRUE)
    # We need to replicate R's behavior: mean([NaN, 1.0]) = NaN
    def r_mean(x):
        """R-style mean: returns NaN if any value is NaN (na.rm=FALSE behavior)"""
        if x.isna().any():
            return np.nan
        return x.mean()
    
    pres_data1 = pd.concat([nutter, nutmar], ignore_index=True)
    pres_data1 = pres_data1.groupby('rgn_id').agg({'val_num': r_mean}).reset_index()
    pres_data1 = pres_data1.rename(columns={'rgn_id': 'region_id', 'val_num': 'value'})

    # Combine all pressure data (R lines 1131-1133)
    pres_data = pd.concat(
        [
            quim.rename(columns={'rgn_id': 'region_id', 'val_num': 'value'})[['region_id', 'value']],
            pat.rename(columns={'rgn_id': 'region_id', 'val_num': 'value'})[['region_id', 'value']],
            bas.rename(columns={'rgn_id': 'region_id', 'val_num': 'value'})[['region_id', 'value']],
            pres_data1,
        ],
        ignore_index=True,
    )

    # Apply R's exact transformation sequence (R lines 1137-1145)
    d_pressures = pres_data.copy()
    d_pressures['value'] = d_pressures['value'].fillna(0)
    d_pressures['pressure'] = 1 - d_pressures['value']
    d_pressures['pressure'] = d_pressures['pressure'].apply(
        lambda x: x + 0.01 if x == 0 else x
    )
    d_pressures = (
        d_pressures.groupby('region_id')
        .apply(lambda x: pd.Series({'score': geometric_mean(x['pressure'])}), include_groups=False)
        .reset_index()
    )
    d_pressures['score'] = d_pressures['score'] * 100
    d_pressures['dimension'] = 'status'
    d_pressures = d_pressures[['region_id', 'score', 'dimension']]

    # ========================================================================
    # TREND CALCULATION
    # ========================================================================

    # Load trend layers (R lines 1150-1163)
    # Note: Trend layers have 'trend' column, not 'val_num'
    quim_trend = layers['data'].get('cw_conquimica_trend')
    if quim_trend is None:
        raise ValueError("Missing layer: cw_conquimica_trend")
    quim_trend = quim_trend[['rgn_id', 'trend']].rename(columns={'trend': 'val_num'})

    pat_trend = layers['data'].get('cw_conpatogenos_tren')
    if pat_trend is None:
        raise ValueError("Missing layer: cw_conpatogenos_tren")
    pat_trend = pat_trend[['rgn_id', 'trend']].rename(columns={'trend': 'val_num'})

    nutmar_trend = layers['data'].get('cw_connutrientesmar_trend')
    if nutmar_trend is None:
        raise ValueError("Missing layer: cw_connutrientesmar_trend")
    nutmar_trend = nutmar_trend[['rgn_id', 'trend']].rename(columns={'trend': 'val_num'})

    nutter_trend = layers['data'].get('cw_connutrientester_trend')
    if nutter_trend is None:
        raise ValueError("Missing layer: cw_connutrientester_trend")
    nutter_trend = nutter_trend[['rgn_id', 'trend']].rename(columns={'trend': 'val_num'})

    bas_trend = layers['data'].get('cw_conbasura_trend')
    if bas_trend is None:
        raise ValueError("Missing layer: cw_conbasura_trend")
    bas_trend = bas_trend[['rgn_id', 'trend']].rename(columns={'trend': 'val_num'})

    # Average nutter and nutmar TREND per region (R lines 1169-1172)
    # Use same R-style mean (returns NaN if any value is NaN)
    trend_data1 = pd.concat([nutter_trend, nutmar_trend], ignore_index=True)
    trend_data1 = trend_data1.groupby('rgn_id').agg({'val_num': r_mean}).reset_index()
    trend_data1 = trend_data1.rename(columns={'rgn_id': 'region_id', 'val_num': 'value'})

    # TODO: VERIFY WITH TEAM - R Bug Replication
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
            quim_trend.rename(columns={'rgn_id': 'region_id', 'val_num': 'value'})[['region_id', 'value']],
            pat_trend.rename(columns={'rgn_id': 'region_id', 'val_num': 'value'})[['region_id', 'value']],
            bas_trend.rename(columns={'rgn_id': 'region_id', 'val_num': 'value'})[['region_id', 'value']],
            pres_data1,  # BUG: Should be trend_data1, but using pres_data1 to match R
        ],
        ignore_index=True,
    )

    # Calculate trend per region (R lines 1179-1184)
    d_trends = trend_data.copy()
    d_trends['trend'] = -1 * d_trends['value']
    d_trends = d_trends.groupby('region_id').agg({'trend': 'mean'}).reset_index()
    d_trends = d_trends.rename(columns={'trend': 'score'})
    d_trends['dimension'] = 'trend'
    d_trends = d_trends[['region_id', 'score', 'dimension']]

    return d_pressures, d_trends
