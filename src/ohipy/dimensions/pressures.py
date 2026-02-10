"""Pressure dimension calculator for OHI."""

import pandas as pd
import numpy as np


def calculate_pressures_all(config, layers):
    """
    Calculate pressure scores for all goals across all regions.
    
    Translates ohicore/R/CalculatePressuresAll.R
    
    Args:
        config: Configuration dictionary from load_config()
        layers: Layers dictionary from load_layers()
    
    Returns:
        DataFrame with columns: goal, dimension, region_id, score
    """
    
    # Load pressure matrix
    p_matrix = config['pressures_matrix'].copy()
    
    # Reshape matrix from wide to long format
    id_cols = ['goal', 'element', 'element_name']
    layer_cols = [c for c in p_matrix.columns if c not in id_cols]
    
    p_matrix = p_matrix.melt(
        id_vars=id_cols,
        value_vars=layer_cols,
        var_name='layer',
        value_name='m_intensity'
    )
    
    # Filter out NA intensities and drop element_name
    p_matrix = p_matrix[p_matrix['m_intensity'].notna()][['goal', 'element', 'layer', 'm_intensity']]
    # Fill NA element with empty string to avoid groupby dropna=True excluding them
    p_matrix['element'] = p_matrix['element'].fillna('')
    
    # Load pressure categories
    p_categories = config['pressure_categories'].copy()
    
    # PATCH: Fix duplicate pres_n_explora in categories which should likely be pres_n_proyexplora
    # Check if duplicate exists
    if len(p_categories[p_categories['layer'] == 'pres_n_explora']) > 1:
        # Find index of duplicates
        dupes = p_categories.index[p_categories['layer'] == 'pres_n_explora'].tolist()
        # Rename the second one to pres_n_proyexplora (assuming it corresponds to line 22)
        if len(dupes) >= 2:
            p_categories.at[dupes[1], 'layer'] = 'pres_n_proyexplora'
    
    # Get pressure element mappings
    # Corrected config access
    p_element = config['config'].get('element_mappings', {}).get('pressures', {})
    
    if p_element:
        p_element_df = pd.DataFrame([
            {'goal': goal, 'layer': layer}
            for goal, layer in p_element.items()
        ])
    else:
        p_element_df = None
    
    # Get gamma weighting
    p_gamma = config['config']['constants']['pressures_gamma']
    
    # Get list of pressure layers
    p_layers = sorted(layer_cols)
    
    # Get regions - load region labels layer
    region_layer_name = config['config']['layers']['region_labels']
    region_layer = layers['data'].get(region_layer_name)
    if region_layer is None:
        raise ValueError(f"Missing region layer: {region_layer_name}")
    
    # Extract region IDs (first numeric column is typically the ID)
    id_col = [c for c in region_layer.columns if 'id' in c.lower() or c == 'rgn_id'][0]
    regions_df = region_layer[[id_col]].copy().rename(columns={id_col: 'region_id'})
    regions_vector = regions_df['region_id'].tolist()
    
    # Create ecological/social weighting
    eco_soc_weight = pd.DataFrame({
        'category': ['ecological', 'social'],
        'weight': [p_gamma, 1 - p_gamma]
    })
    
    # Handle scenario data years
    if 'scenario_data_years' in config and len(config['scenario_data_years']) > 0:
        scenario_data_year = config['scenario_data_years'].copy()
        scenario_data_year = scenario_data_year[
            scenario_data_year['layer_name'].isin(p_layers)
        ]
        scenario_data_year = scenario_data_year[
            scenario_data_year['scenario_year'] == layers['data']['scenario_year']
        ][['layer_name', 'data_year']].rename(columns={'layer_name': 'layer', 'data_year': 'year'})
        
        # Add layers without years
        layers_no_years = set(p_layers) - set(scenario_data_year['layer'])
        if layers_no_years:
            no_years_df = pd.DataFrame({
                'layer': list(layers_no_years),
                'year': 20100
            })
            scenario_data_year = pd.concat([scenario_data_year, no_years_df], ignore_index=True)
    else:
        scenario_data_year = pd.DataFrame({
            'layer': p_layers,
            'year': 20100
        })
    
    # Load pressure layer data - collect all layers
    p_rgn_layers_list = []
    for layer_name in p_layers:
        layer_data = layers['data'].get(layer_name)
        if layer_data is None:
            continue
        
        df = layer_data.copy()
        
        # Find ID column
        id_col = [c for c in df.columns if 'id' in c.lower() or c == 'rgn_id']
        if not id_col:
            continue
        id_col = id_col[0]
        
        # Find value column (typically 'val_num' or 'value')
        val_col = [c for c in df.columns if c in ['val_num', 'value']]
        if not val_col:
            # Take first non-id, non-year column
            val_col = [c for c in df.columns if c not in [id_col, 'year']]
            if not val_col:
                continue
        val_col = val_col[0]
        
        # Prepare data
        cols_to_keep = [id_col, val_col]
        if 'year' in df.columns:
            cols_to_keep.append('year')
            df = df[cols_to_keep].copy()
        else:
            df = df[cols_to_keep].copy()
            df['year'] = np.nan
        
        df = df.rename(columns={id_col: 'region_id', val_col: 'val_num'})
        df['layer'] = layer_name
        
        p_rgn_layers_list.append(df)
    
    if not p_rgn_layers_list:
        raise ValueError("No pressure layer data found")
    
    p_rgn_layers_data = pd.concat(p_rgn_layers_list, ignore_index=True)
    
    # Filter and prepare data
    p_rgn_layers_data = p_rgn_layers_data[
        p_rgn_layers_data['region_id'].isin(regions_vector)
    ]
    p_rgn_layers_data = p_rgn_layers_data[p_rgn_layers_data['val_num'].notna()]
    p_rgn_layers_data['year'] = p_rgn_layers_data['year'].fillna(20100)
    
    # Join with scenario years
    p_rgn_layers = scenario_data_year.merge(p_rgn_layers_data, on=['year', 'layer'])
    p_rgn_layers = p_rgn_layers[['region_id', 'val_num', 'layer']]
    
    # Check dropped layers
    dropped_layers = set(p_rgn_layers_data['layer'].unique()) - set(p_rgn_layers['layer'].unique())
    
    # Merge matrix with categories
    p_matrix = p_matrix.merge(p_categories, on='layer')
    
    # Calculate max intensity per subcategory
    p_matrix['max_subcategory'] = p_matrix.groupby(
        ['goal', 'element', 'category', 'subcategory']
    )['m_intensity'].transform('max')
    
    # Merge with region data
    rgn_matrix = p_matrix.merge(p_rgn_layers, on='layer')
    
    # Calculate pressure intensity
    rgn_matrix['pressure_intensity'] = rgn_matrix['m_intensity'] * rgn_matrix['val_num']
    
    # Debug AO 1101 social layers
    ao_soc_debug = rgn_matrix[
        (rgn_matrix['goal'] == 'AO') & 
        (rgn_matrix['region_id'] == 1101) & 
        (rgn_matrix['category'] == 'social')
    ]
    
    # Separate ecological and social pressures
    # Ecological: sum / 3, capped at 1
    calc_pressure_eco = rgn_matrix[rgn_matrix['category'] == 'ecological'].groupby(
        ['goal', 'element', 'category', 'subcategory', 'max_subcategory', 'region_id']
    )['pressure_intensity'].sum().reset_index()
    calc_pressure_eco['cum_pressure'] = (calc_pressure_eco['pressure_intensity'] / 3).clip(upper=1)
    
    # Debug AO 1101 eco
    ao_1101_eco = calc_pressure_eco[
        (calc_pressure_eco['goal'] == 'AO') & (calc_pressure_eco['region_id'] == 1101)
    ]
    
    calc_pressure_eco = calc_pressure_eco.drop(columns=['pressure_intensity'])
    
    # Social: mean, capped at 1
    calc_pressure_soc = rgn_matrix[rgn_matrix['category'] == 'social'].groupby(
        ['goal', 'element', 'category', 'subcategory', 'max_subcategory', 'region_id']
    )['pressure_intensity'].mean().reset_index()
    calc_pressure_soc['cum_pressure'] = calc_pressure_soc['pressure_intensity'].clip(upper=1)
    
    # Debug AO 1101 soc
    ao_1101_soc = calc_pressure_soc[
        (calc_pressure_soc['goal'] == 'AO') & (calc_pressure_soc['region_id'] == 1101)
    ]

    calc_pressure_soc = calc_pressure_soc.drop(columns=['pressure_intensity'])
    
    # Combine ecological and social
    calc_pressure = pd.concat([calc_pressure_eco, calc_pressure_soc], ignore_index=True)
    
    # Weighted mean of subcategories (weighted by max_subcategory)
    def weighted_mean(group):
        weights = group['max_subcategory'].astype(float)
        values = group['cum_pressure'].astype(float)
        if weights.sum() == 0:
            return np.nan
        return np.average(values, weights=weights)
    
    calc_pressure = calc_pressure.groupby(
        ['goal', 'element', 'category', 'region_id']
    ).apply(weighted_mean, include_groups=False).reset_index(name='pressure')
    
    # Combine ecological and social using gamma weighting
    calc_pressure = calc_pressure.merge(eco_soc_weight, on='category')
    
    def weighted_mean_gamma(group):
        weights = group['weight'].astype(float)
        values = group['pressure'].astype(float)
        if weights.sum() == 0:
            return np.nan
        return np.average(values, weights=weights)
    
    calc_pressure = calc_pressure.groupby(
        ['goal', 'element', 'region_id']
    ).apply(weighted_mean_gamma, include_groups=False).reset_index(name='pressure')
    
    # Handle goals with elements
    if p_element_df is not None and len(p_element_df) > 0:
        
        # Load element weight layers
        p_element_layers_list = []
        for layer_name in p_element_df['layer'].unique():
            layer_data = layers['data'].get(layer_name)
            if layer_data is None:
                continue
            
            df = layer_data.copy()
            
            # Find ID column
            id_col = [c for c in df.columns if 'id' in c.lower() or c == 'rgn_id']
            if not id_col:
                continue
            id_col = id_col[0]
            
            # Find category/element column
            # Known element columns from debug: 'producto', 'habitat', 'sector', 'boolean'(likely value not cat?), 'category'
            # Heuristic: Find string/object column that isn't ID or 'year'
            # Or check specific known names
            known_cat_cols = ['category', 'habitat', 'sector', 'producto', 'spp', 'species']
            cat_col = [c for c in df.columns if c.lower() in known_cat_cols]
            
            if cat_col:
                cat_col = cat_col[0]
            else:
                # Fallback: look for object/string column
                obj_cols = [c for c in df.columns if df[c].dtype == 'object' or df[c].dtype == 'string']
                # Exclude ID if it was detected as object
                obj_cols = [c for c in obj_cols if c != id_col and c != 'year']
                if obj_cols:
                    cat_col = obj_cols[0]
                else:
                    continue
            
            # Find value column
            # Known value columns: 'weight', 'value', 'boolean', 'area_km2', 'val_num'
            known_val_cols = ['val_num', 'value', 'weight', 'boolean', 'area_km2', 'score']
            val_col = [c for c in df.columns if c.lower() in known_val_cols]
            
            if val_col:
                val_col = val_col[0]
            else:
                # Fallback: take first numeric column that isn't ID or year
                num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
                num_cols = [c for c in num_cols if c != id_col and c != 'year']
                if num_cols:
                    val_col = num_cols[0]
                else:
                    continue
            
            df = df[[id_col, cat_col, val_col]].copy()
            df = df.rename(columns={id_col: 'region_id', cat_col: 'element', val_col: 'element_wt'})
            df['layer'] = layer_name
            
            p_element_layers_list.append(df)
        
        # Even if list is empty (shouldn't be now), we need to ensure aggregation happens
        # But if list empty, we can't merge weights.
        # We must proceed to aggregation step regardless of valid layers, 
        # but we need a dataframe structure for the merge.
        
        if p_element_layers_list:
            p_element_layers = pd.concat(p_element_layers_list, ignore_index=True)
            p_element_layers = p_element_layers[p_element_layers['region_id'].isin(regions_vector)]
            p_element_layers = p_element_layers[p_element_layers['element'].notna()]
            p_element_layers = p_element_layers[p_element_layers['element_wt'].notna()]
            
            # Merge with goal mapping
            p_element_layers = p_element_layers.merge(p_element_df, on='layer')
            p_element_layers = p_element_layers[['region_id', 'goal', 'element', 'element_wt']]
            p_element_layers['element'] = p_element_layers['element'].astype(str)
            
            # Merge with pressure calculations
            calc_pressure = calc_pressure.merge(
                p_element_layers,
                on=['region_id', 'goal', 'element'],
                how='left'
            )
        else:
             # If no element layers loaded, add empty element_wt column
             calc_pressure['element_wt'] = np.nan

        # Filter out rows where element_wt is NA for goals that have elements
        goals_with_elements = p_element_df['goal'].unique()
        
        # Keep rows if:
        # 1. Goal is NOT in goals_with_elements (preserves CS, AO etc)
        # 2. Goal IS in goals_with_elements AND element_wt is NOT NA (matches valid element)
        
        # Note: If a goal is in goals_with_elements but we failed to load its weights, 
        # we might drop all its rows! This is desired behavior (if weights missing, data invalid).
        
        calc_pressure = calc_pressure[
            ~((calc_pressure['element_wt'].isna()) & (calc_pressure['goal'].isin(goals_with_elements)))
        ]
        
        # Fill NA element_wt with 1 for goals without elements (or CS which isn't in p_element)
        calc_pressure['element_wt'] = calc_pressure['element_wt'].fillna(1)
        
        # Weighted mean by element
        def weighted_mean_element(group):
            weights = group['element_wt'].astype(float)
            values = group['pressure'].astype(float)
            if weights.sum() == 0:
                return np.nan
            return np.average(values, weights=weights)
        
        calc_pressure = calc_pressure.groupby(
            ['goal', 'region_id']
        ).apply(weighted_mean_element, include_groups=False).reset_index(name='pressure')
    
    # Merge with regions and format output
    scores = regions_df.merge(calc_pressure, on='region_id', how='left')
    scores['dimension'] = 'pressures'
    scores = scores[['goal', 'dimension', 'region_id', 'pressure']].rename(columns={'pressure': 'score'})
    scores['score'] = (scores['score'] * 100).round(2)
    
    # Remove rows with NA scores
    scores = scores[scores['score'].notna()]
    
    return scores
