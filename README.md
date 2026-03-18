# OHI Python Validation

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

Go to `comparative/images/R` folder and run the following commands:

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
time docker run --rm -v "$PWD":/home/project -w /home/project ohicore-r-env Rscript comparative/calculate_scores.r
```

This will create `comparative/scores_2024_r.csv`

### Run Python Implementation

At the root of the project, run (you need to install uv before):

```bash
uv sync
```

And then:

```bash
time uv run python scripts/run_python_scores.py
```

That will generate the Python scores files at `comparative/scores_2024_py.csv`. To check if they match with R scores (at the root of the project):

```bash
uv run python comparative/compare_scores.py
```

The comparison script outputs a SUCESS/FAILURE summary and writes `comparative/scores_difference.csv` with more details for the differences. This the single source of truth for pass/fail.

## Testing

### Run All Tests
```bash
uv run pytest tests/ -v
```

### Unit Tests
```bash
uv run pytest tests/ -v --ignore=tests/test_parity_full.py
```

### Parity Tests (R vs Python)
Parity tests validate that Python produces identical output to R reference implementation.

**Test Coverage:**
- 44 tests total across 4 datasets × 11 variations
- Datasets: original, noise_1pct, noise_5pct, noise_10pct
- Variations: baseline, 4 weight modifications, 3 pressure modifications, 3 resilience modifications

**Prerequisites:**
- Docker installed and running
- `chl/` repository cloned (for R files)
- R fixtures pre-generated in `comparative/fixtures/`

**Run Parity Tests:**
```bash
uv run pytest tests/test_parity_full.py -v
```

**Regenerate R Fixtures (if needed):**
```bash
# Setup fixtures for all noise levels
uv run python -m tests.parity.setup_fixtures

# Or regenerate R scores via Docker
docker run --rm -v "$PWD":/home/project -w /home/project ohicore-r-env Rscript comparative/calculate_scores.r
```

### Noise Injection Testing
The testing framework uses random sampling noise injection to test robustness:
- **Random sampling**: Replaces values with random samples from the original distribution
- **Noise levels**: 1%, 5%, 10% of values modified
- **Null preservation**: Null values are tracked and restored after noise injection

## TODO

- modify config files to make it easier the reading of files, config:
  - to remove pressures or resiliences easily
  - to change the input layers
- wrap the calculator into a multi-year capable script (with the data layers)
- make repo public
- check the probable R Bug Replication in cw.py

## TODO (more)

- Create Docker version for python implementation. 
- Create AWS Lambda version for python implementation
- Create Sphinx documentation
- Create User guides
- Github actions CI/CD