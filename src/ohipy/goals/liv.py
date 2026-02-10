"""LIV Goal - Livelihoods

Calculates status and trend for the Livelihoods goal based on jobs and wages.

Algorithm (from ohi-science-chl/comunas/conf/functions.R lines 704-845):
1. Load wages, jobs, workforce size, unemployment data
2. Apply job multipliers by sector
3. Adjust jobs by employment proportion
4. Status: Compare current vs 5-year-ago values for jobs (sum) and wages (avg)
5. Trend: Linear regression on jobs and wages by sector, weighted average
"""

import pandas as pd
import numpy as np
from scipy import stats


def LIV(layers):
    """
    Calculate LIV (Livelihoods) goal status and trend.

    Args:
        layers: Layers dictionary from load_layers()

    Returns:
        tuple: (status_df, trend_df) where each is a DataFrame with columns:
               [region_id, score, dimension]
    """
    # STEP 1: Load layers
    le_wages_layer = layers['data'].get('le_wage_sector')
    if le_wages_layer is None:
        raise ValueError("Missing layer: le_wage_sector")
    le_wages = le_wages_layer.copy()
    le_wages = le_wages.rename(columns={'wage': 'wage_usd'})
    le_wages = le_wages[['rgn_id', 'year', 'sector', 'wage_usd']]

    le_jobs_layer = layers['data'].get('le_jobs_sector')
    if le_jobs_layer is None:
        raise ValueError("Missing layer: le_jobs_sector")
    le_jobs = le_jobs_layer.copy()
    le_jobs = le_jobs[['rgn_id', 'year', 'sector', 'jobs']]

    le_workforce_layer = layers['data'].get('le_workforcesize_adj')
    if le_workforce_layer is None:
        raise ValueError("Missing layer: le_workforcesize_adj")
    le_workforce_size = le_workforce_layer.copy()
    le_workforce_size = le_workforce_size.rename(columns={'jobs': 'jobs_all'})
    le_workforce_size = le_workforce_size[['rgn_id', 'year', 'jobs_all']]

    le_unemployment_layer = layers['data'].get('le_unemployment')
    if le_unemployment_layer is None:
        raise ValueError("Missing layer: le_unemployment")
    le_unemployment = le_unemployment_layer.copy()
    le_unemployment = le_unemployment.rename(columns={'percent': 'pct_unemployed'})
    le_unemployment = le_unemployment[['rgn_id', 'year', 'pct_unemployed']]

    # STEP 2: Define multipliers
    multipliers_jobs = pd.DataFrame({
        'sector': ['Turismo', 'Pesca', 'Acuicultura', 'Alojamiento', 'Transporte'],
        'multiplier': [1, 1.582, 2.7, 1, 1]
    })

    # STEP 3: Calculate employment
    le_employed = le_workforce_size.merge(le_unemployment, on=['rgn_id', 'year'], how='left')
    le_employed['proportion_employed'] = (100 - le_employed['pct_unemployed']) / 100
    le_employed['employed'] = le_employed['jobs_all'] * le_employed['proportion_employed']

    # Convert rgn_id to string, pad, then back to int (mimicking R code)
    le_employed['rgn_id'] = le_employed['rgn_id'].astype(str).str.zfill(5).astype(int)

    # STEP 4: Build liv dataset
    liv = le_jobs.merge(multipliers_jobs, on='sector', how='left')
    liv['jobs_mult'] = liv['jobs'] * liv['multiplier']
    liv = liv.merge(le_employed, on=['rgn_id', 'year'], how='left')
    liv['jobs_adj'] = liv['jobs_mult'] * liv['proportion_employed']
    liv = liv.merge(le_wages, on=['rgn_id', 'year', 'sector'], how='left')
    liv = liv.sort_values(['year', 'sector', 'rgn_id'])

    # STEP 5: Calculate status
    liv_status1 = liv[~liv['jobs_adj'].isna() & ~liv['wage_usd'].isna()].copy()

    max_year = liv_status1['year'].max()
    liv_status = liv_status1[liv_status1['year'] >= max_year - 4].copy()

    # Summarize across sectors
    liv_status = liv_status.sort_values(['rgn_id', 'year', 'sector'])
    liv_status = liv_status.groupby(['rgn_id', 'year']).agg({
        'jobs_adj': 'sum',
        'wage_usd': 'mean'
    }).reset_index()
    liv_status = liv_status.rename(columns={'jobs_adj': 'jobs_sum', 'wage_usd': 'wages_avg'})

    # For each region, get first year values
    liv_status = liv_status.sort_values(['rgn_id', 'year'])
    liv_status['jobs_sum_first'] = liv_status.groupby('rgn_id')['jobs_sum'].transform('first')
    liv_status['wages_avg_first'] = liv_status.groupby('rgn_id')['wages_avg'].transform('first')

    # Calculate scores
    liv_status['x_jobs'] = (liv_status['jobs_sum'] / liv_status['jobs_sum_first']).clip(-1, 1)
    liv_status['x_wages'] = (liv_status['wages_avg'] / liv_status['wages_avg_first']).clip(-1, 1)
    liv_status['score'] = ((liv_status['x_jobs'] + liv_status['x_wages']) / 2) * 100

    # Filter to most recent year
    liv_status = liv_status[liv_status['year'] == max_year].copy()
    liv_status = liv_status.rename(columns={'rgn_id': 'region_id'})
    liv_status['dimension'] = 'status'
    liv_status = liv_status[['region_id', 'score', 'dimension']]

    # STEP 6: Calculate trend
    liv_trend_data = liv[~liv['jobs_adj'].isna() & ~liv['wage_usd'].isna()].copy()
    max_year_trend = liv_trend_data['year'].max()
    liv_trend_data = liv_trend_data[liv_trend_data['year'] >= max_year_trend - 4].copy()

    # Get sector weight
    liv_trend_data = liv_trend_data.sort_values(['rgn_id', 'year', 'sector'])
    liv_trend_data['weight'] = liv_trend_data.groupby(['rgn_id', 'sector'])['jobs_adj'].transform('sum')

    # Melt ALL value columns into single metric (mimicking R's melt behavior)
    # R melts all columns except the id columns
    id_cols = ['rgn_id', 'year', 'sector', 'weight']
    value_cols = [c for c in liv_trend_data.columns if c not in id_cols]

    liv_trend_melt = liv_trend_data.melt(
        id_vars=id_cols,
        value_vars=value_cols,
        var_name='metric',
        value_name='value'
    )

    # Calculate trend per metric-region-sector
    def calc_sector_trend(group):
        if len(group) < 2:
            return pd.Series({'sector_trend': 0.0})

        years = group['year'].values
        values = group['value'].values

        slope, intercept, r_value, p_value, std_err = stats.linregress(years, values)
        sector_trend = slope * 5
        sector_trend = max(-1, min(1, sector_trend))

        return pd.Series({'sector_trend': sector_trend})

    liv_trend_calc = liv_trend_melt.groupby(['metric', 'rgn_id', 'sector', 'weight'], group_keys=False).apply(
        calc_sector_trend
    ).reset_index()

    # Weighted mean across sectors per region-metric
    liv_trend_by_metric = liv_trend_calc.groupby(['metric', 'rgn_id']).apply(
        lambda x: pd.Series({
            'metric_trend': np.average(x['sector_trend'], weights=x['weight'])
        })
    ).reset_index()

    # Mean across metrics per region
    liv_trend = liv_trend_by_metric.groupby('rgn_id').agg({
        'metric_trend': 'mean'
    }).reset_index()

    liv_trend = liv_trend.rename(columns={'rgn_id': 'region_id', 'metric_trend': 'score'})
    liv_trend['dimension'] = 'trend'
    liv_trend = liv_trend[['region_id', 'score', 'dimension']]

    # STEP 7: Filter out NaN scores
    livna = liv_status[liv_status['score'].isna() | (liv_status['score'].apply(lambda x: np.isnan(x) if isinstance(x, float) else False))]
    livna_regions = livna['region_id'].unique()

    liv_status = liv_status[~liv_status['region_id'].isin(livna_regions)]
    liv_trend = liv_trend[~liv_trend['region_id'].isin(livna_regions)]

    return liv_status, liv_trend
