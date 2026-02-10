"""OHI Configuration Module - Load configuration and metadata from YAML and CSV files."""

import os
from pathlib import Path
import yaml
import pandas as pd


def load_config(config_path=None):
    """
    Load OHI configuration from YAML and CSV files.

    Args:
        config_path: Optional path to config.yaml. If None, uses default location.

    Returns:
        dict: Configuration dictionary with keys:
            - config: YAML configuration data
            - goals: DataFrame from goals.csv
            - pressures_matrix: DataFrame from pressures_matrix.csv
            - resilience_matrix: DataFrame from resilience_matrix.csv
            - pressure_categories: DataFrame from pressure_categories.csv
            - resilience_categories: DataFrame from resilience_categories.csv
            - layers: DataFrame from layers.csv
            - scenario_data_years: DataFrame from scenario_data_years.csv
    """
    # Determine config file location
    if config_path is None:
        # Default: python/ohi/config/config.yaml
        config_dir = Path(__file__).parent
        config_path = config_dir / 'config.yaml'
    else:
        config_path = Path(config_path)

    # Read YAML configuration
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Determine project root (3 levels up from this file: ohi/config/__init__.py -> ohi -> python -> root)
    project_root = Path(__file__).parent.parent.parent.parent

    # Load CSV files
    paths = config['paths']

    # Helper to resolve path relative to project root
    def resolve_path(rel_path):
        return project_root / rel_path

    # Load goals.csv
    goals_df = pd.read_csv(resolve_path(paths['goals_csv']))

    # Load pressure matrix
    pressures_matrix_df = pd.read_csv(resolve_path(paths['pressures_matrix_csv']))

    # Load resilience matrix
    resilience_matrix_df = pd.read_csv(resolve_path(paths['resilience_matrix_csv']))

    # Load pressure categories
    pressure_categories_df = pd.read_csv(resolve_path(paths['pressure_categories_csv']))

    # Load resilience categories
    resilience_categories_df = pd.read_csv(resolve_path(paths['resilience_categories_csv']))

    # Load layers metadata
    layers_df = pd.read_csv(resolve_path(paths['layers_csv']))

    # Load scenario data years
    scenario_data_years_df = pd.read_csv(resolve_path(paths['scenario_data_years_csv']))

    # Return unified configuration
    return {
        'config': config,
        'goals': goals_df,
        'pressures_matrix': pressures_matrix_df,
        'resilience_matrix': resilience_matrix_df,
        'pressure_categories': pressure_categories_df,
        'resilience_categories': resilience_categories_df,
        'layers': layers_df,
        'scenario_data_years': scenario_data_years_df
    }


# Module exports
__all__ = ['load_config']
