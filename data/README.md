# Data Directory

Data files for Ocean Health Index (OHI) calculations. Migrated from `chl/comunas/` submodule.

## Structure

```
data/
├── conf/                   # Configuration files (6 CSVs)
│   ├── goals.csv                  # Goal definitions and weights
│   ├── pressures_matrix.csv       # Pressure-goal mapping
│   ├── resilience_matrix.csv      # Resilience-goal mapping
│   ├── pressure_categories.csv    # Pressure category definitions
│   ├── resilience_categories.csv  # Resilience category definitions
│   └── scenario_data_years.csv    # Layer-year mappings
├── layers.csv              # Layer metadata (99 rows)
└── layers/
    ├── csv/                # CSV layer files (227 files)
    └── parquet/            # Parquet layer files (227 files)
```

## Layer Files

Both CSV and Parquet formats are provided:

- **Parquet** (preferred): Faster loading, smaller files
- **CSV**: More compatible, human-readable

The `load_layers()` function prefers Parquet by default but falls back to CSV if Parquet files are unavailable.

## Layer Metadata

`layers.csv` maps layer names to filenames:

| Column | Description |
|--------|-------------|
| layer | Layer name (e.g., `fis_b_bmsy`) |
| filename | File path (e.g., `fis_b_bmsy_chl2024.csv`) |

## Source

Data migrated from `chl/comunas/` (git submodule pointing to https://github.com/OHI-Science/chl). The submodule is kept for R comparison scripts but Python code uses this `data/` folder.

## Usage

```python
from ohipy.config import load_config
from ohipy.layers import load_layers

config = load_config()
layers = load_layers(config)
```

Control format preference via `config.yaml`:

```yaml
layer_format: "parquet"  # or "csv"
```

Or via CLI:

```bash
uv run python scripts/run_python_scores.py --format csv
uv run python scripts/run_python_scores.py --format parquet
```
