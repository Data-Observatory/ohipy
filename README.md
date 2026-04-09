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

At the root of the project, run (you need to install uv before):

```bash
uv sync
```

And then:

```bash
time uv run python scripts/run_python_scores.py
```

That will generate the Python scores files at `tests/comparative/scores_2024_py.csv`. To check if they match with R scores (at the root of the project):

```bash
uv run python tests/comparative/compare_scores.py
```

The comparison script outputs a SUCESS/FAILURE summary and writes `tests/comparative/scores_difference.csv` with more details for the differences. This the single source of truth for pass/fail.

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

## TODO

- modify config files to make it easier the reading of files, config:
  - to remove pressures or resiliences easily
  - to change the input layers
- wrap the calculator into a multi-year capable script (with the data layers)
- make repo public
- check the probable R Bug Replication in cw.py
- Install Repository Settings (https://github.com/apps/repository-settings) GitHub App on the repo — this reads .github/settings.yml to enforce branch protection
- Install Codecov (https://github.com/apps/codecov) GitHub App — this reads the coverage.xml artifact and generates the badge

## TODO (more)

- Create Docker version for python implementation. 
- Create AWS Lambda version for python implementation
- Create Sphinx documentation
- Create User guides
- Github actions CI/CD