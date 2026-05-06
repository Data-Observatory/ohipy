# OHI Python Validation

[![CI](https://github.com/Data-Observatory/ohipy/actions/workflows/ci.yml/badge.svg)](https://github.com/Data-Observatory/ohipy/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Data-Observatory/ohipy/branch/main/graph/badge.svg)](https://codecov.io/gh/Data-Observatory/ohipy)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)

## Setup

### Data Directory

The `data/` directory contains configuration and layer files used by the Python implementation. It is included in the repository and does not require additional setup. This directory includes:
- `data/conf/`: Configuration files (goals.csv, etc.)
- `data/layers/`: Layer data files
- `data/layers.csv`: Layer metadata

### Clone OHI core chl (for R validation only)

If you want to validate Python scores against R implementation, clone the reference repository at the root of the project:

```bash
git clone https://github.com/OHI-Science/chl
```

This is **only needed for R comparison**. The Python calculation uses `data/` directory.

### Deploy R docker image

Go to `tests/comparative/images/R` folder and run the following commands:

```bash
# Build the container
docker build -t ohicore-r-env .

# Check that the container is working and has the correct version of dplyr (1.0.10)
docker run --rm ohicore-r-env R -e "library(ohicore); sessionInfo(); packageVersion('dplyr')"

# If you want to run an interactive session inside the container, you can use the following command:
docker run -it --rm ohicore-r-env /bin/bash
```

#### Why a Docker iamge?

As the needed packages are older versiones, we need to have dplyr <= 1.0.10. Newer versions of dplyr will not work with the code in this repo due to some changes in the behavior of the `group_by` function

Even forcing this version, sometimes it doesnt works as other packages force the version update, so the docker solution is the best way to achieve this.

### Create scores to compare

Go to the root folder and run (on windows powershell this will fail!!):

```bash
# Run the script to calculate the scores
time docker run --rm -v "$PWD":/home/project -w /home/project ohicore-r-env Rscript tests/comparative/calculate_scores.r
```

This will create `tests/comparative/scores_2024_r.csv`

### Run Python Implementation

At the root of the project, run:

```bash
uv sync
```

See the [Usage](#usage) section below for full documentation of the Python API and CLI arguments.

To generate Python scores and compare with R reference scores:

```bash
time uv run python scripts/run_python_scores.py
uv run python tests/comparative/compare_scores.py
```

The comparison script outputs a SUCCESS/FAILURE summary and writes `tests/comparative/scores_difference.csv` with details on any differences. This is the single source of truth for pass/fail.

## Usage

### Python API

The `OHIPipeline` class provides a one-call interface for OHI calculations:

```python
from ohipy.pipeline import OHIPipeline

pipeline = OHIPipeline()  # uses data/ in project root
scores = pipeline.run(year=2024)
```

**Return value:** A Polars DataFrame with columns:
- `goal` — Goal code (e.g., "FIS", "MAR", "Index")
- `dimension` — Calculation stage ("status", "trend", "pressures", "resilience", "future", "score")
- `region_id` — Region identifier (0 = global, >0 = specific region)
- `score` — Numeric score (0-100 for most dimensions, -1 to 1 for trend)

#### Year

Sets the scenario year, which determines which data years are used via the `scenario_data_years.csv` mapping. Multi-year layers (like fisheries data) will use the data year corresponding to the scenario year.

```python
scores_2024 = pipeline.run(year=2024)
scores_2021 = pipeline.run(year=2021)
```

Different years may produce different status and trend scores when underlying data layers have year-specific values.

#### Data Path

Points to the base directory containing `data/conf/`, `data/layers/`, and `data/layers.csv`. Use this to run calculations on alternative datasets or simulation results.

```python
# Production data (default)
pipeline = OHIPipeline()

# Custom simulation dataset
pipeline = OHIPipeline("simulations/scenario_a")
```

The path is resolved relative to the current working directory. Config paths in `config.yaml` (e.g., `data/conf/goals.csv`) are resolved relative to this base path.

#### Goal Weights

Override the default goal weights from `goals.csv`. Weights are normalized to sum to 1 internally. This affects how sub-goals aggregate into the Index score.

Available goal codes: FIS, MAR, FP, AO, NP, CS, CP, TR, LIV, ECO, LE, ICO, LSP, SP, CW, HAB, SPP, BD

```python
# Emphasize fisheries, de-emphasize mariculture
scores = pipeline.run(weights={"FIS": 2.0, "MAR": 0.5})

# Extreme weight change produces different Index scores
scores = pipeline.run(weights={"FIS": 100.0, "MAR": 0.001})
```

#### Disable Pressure/Resilience Columns

Remove specific pressure or resilience columns from the calculation matrices. This affects how pressures and resilience scores are computed for goals that depend on those columns.

Common pressure columns include: cw_conquimica, cw_conpatogenos, cw_connutrientesmar, cw_conbasura, cw_conindustrial, sp_invasoras, des_habitat_marino, des_habitat_costero, traf_maritimo, den_cencultivo, turismo_cost, pes_ilegal, inst_artesdepesca, cc_anomaliast, cc_sataragonita, cc_cotaind, pres_n_explora, pres_n_opa, pres_n_ocomunitarias, pres_n_fipa, pres_n_proyexplora, pres_s_muniverde, pres_lim_playas, pres_in_municipales, pres_scam, pres_com_ccee, pres_com_prd, pres_con_eerr, pres_est_rrdd

```python
# Remove a single pressure source
scores = pipeline.run(disable=["cw_conpatogenos"])

# Remove multiple sources
scores = pipeline.run(disable=["cw_conpatogenos", "cw_connutrientesmar"])
```

The `disable` list removes columns from **both** the pressure and resilience matrices.

#### Skip Dimensions

Skip entire dimension calculations and use neutral values instead:
- `skip_pressures=True` — all pressure scores set to 0.0 (no pressure effect)
- `skip_resilience=True` — all resilience scores set to 100.0 (perfect resilience)

```python
# Calculate without pressures
scores = pipeline.run(skip_pressures=True)

# Calculate without resilience
scores = pipeline.run(skip_resilience=True)

# Calculate with only status and trend
scores = pipeline.run(skip_pressures=True, skip_resilience=True)
```

Useful for sensitivity analysis to isolate the effect of individual dimensions.

### CLI

The `run_python_scores.py` script exposes the same functionality via command line. All parameters mirror the Python API.

#### Year

Sets the assessment year for the calculation.

```bash
uv run python scripts/run_python_scores.py --year 2023
```

#### Data Path

Points to a custom dataset directory.

```bash
uv run python scripts/run_python_scores.py --data-path simulations/scenario_a
```

#### Goal Weights

Override default goal weights using a JSON string. Available goal codes: FIS, MAR, FP, AO, NP, CS, CP, TR, LIV, ECO, LE, ICO, LSP, SP, CW, HAB, SPP, BD

```bash
# Emphasize fisheries, de-emphasize mariculture
uv run python scripts/run_python_scores.py --weights '{"FIS": 2.0, "MAR": 0.5}'
```

#### Disable Pressure/Resilience Columns

Remove pressure or resilience columns from both matrices.

```bash
# Remove a single pressure source
uv run python scripts/run_python_scores.py --disable cw_conpatogenos

# Remove multiple sources
uv run python scripts/run_python_scores.py --disable cw_conpatogenos,cw_connutrientesmar
```

#### Skip Dimensions

Skip pressure or resilience calculations entirely.

```bash
# Calculate without pressures
uv run python scripts/run_python_scores.py --skip-pressures

# Calculate without resilience
uv run python scripts/run_python_scores.py --skip-resilience

# Calculate with only status and trend
uv run python scripts/run_python_scores.py --skip-pressures --skip-resilience
```

#### Output Path

Write scores to a custom location instead of the default `tests/comparative/scores_2024_py.csv`.

```bash
uv run python scripts/run_python_scores.py --output results/scores.csv
```

#### Custom Layers Metadata

Use a custom `layers.csv` file when layer filenames differ from the defaults. The file must have the same columns as the default `data/layers.csv` (at minimum: `layer`, `filename`).

```bash
uv run python scripts/run_python_scores.py --layers-csv /path/to/my_layers.csv
```

## Testing

### Quick Start

```bash
# Full test suite (Docker, fixtures, all tests)
./tests/run_all_tests.sh

# Smoke test (unit tests only, no Docker needed)
./tests/run_all_tests.sh --skip-docker --no-fixtures

# Unit tests only
uv run pytest tests/ -v
```

For detailed documentation on all test categories, fixtures, and variations, see [tests/README.md](tests/README.md).

## Docker

A lightweight Docker image is available for running calculations without a local Python setup. The default `data/` directory is baked into the image.

### Build

```bash
docker build -t ohipy .
```

### Run

```bash
# Default (year 2024, baked-in data)
docker run --rm -v $(pwd)/results:/output ohipy

# Custom year
docker run --rm -v $(pwd)/results:/output ohipy --year 2023

# Custom data directory (overrides baked-in data)
docker run --rm -v /path/to/my/data:/app/data -v $(pwd)/results:/output ohipy

# With goal weights
docker run --rm -v $(pwd)/results:/output ohipy --weights '{"FIS": 2.0, "MAR": 0.5}'

# Disable pressure columns
docker run --rm -v $(pwd)/results:/output ohipy --disable cw_conpatogenos,cw_connutrientesmar

# Skip dimensions
docker run --rm -v $(pwd)/results:/output ohipy --skip-pressures --skip-resilience

# Full custom: custom data + params + output filename
docker run --rm \
  -v /path/to/sim_data:/app/data \
  -v $(pwd)/results:/output \
  ohipy --year 2023 --weights '{"FIS": 2.0}' --output /output/scores_2023.csv

# Custom layers.csv (e.g. layer filenames differ from defaults)
docker run --rm \
  -v /path/to/my_layers.csv:/custom/layers.csv \
  -v /path/to/my/data:/app/data \
  -v $(pwd)/results:/output \
  ohipy --layers-csv /custom/layers.csv
```

All CLI parameters from the [CLI](#cli) section pass through directly: `--year`, `--data-path`, `--weights`, `--disable`, `--skip-pressures`, `--skip-resilience`, `--output`, `--layers-csv`.

## TODO

- make repo public
- check the probable R Bug Replication in cw.py
- Create Docker version for python implementation
- Create AWS Lambda version for python implementation
- Create Sphinx documentation
- Create User guides