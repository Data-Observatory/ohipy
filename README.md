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

### Unit Tests
Run the unit test suite:
```bash
uv run pytest tests/
```

### Integration Tests (R vs Python Parity)
Integration tests compare Python scores against R reference implementation.

**Prerequisites:**
- Docker installed and running
- `chl/` repository cloned (for R files)
- Run setup script first

**Setup:**
```bash
# Clone R reference repository (one-time)
git clone https://github.com/OHI-Science/chl

# Setup test data
uv run python tests/scripts/setup_test_data.py --force
```

**Run Integration Tests:**
```bash
# Run all integration tests
uv run python tests/scripts/run_integration_tests.py --setup --noise-levels 0,0.01,0.05
```

### Noise Injection Testing
The testing framework supports noise injection to test robustness:
- **Gaussian noise**: `sigma_pct` parameter (0.01 = 1% noise)
- **Bootstrap resampling**: `frac` parameter (0.8 = 80% of data)

## TODO

- modify config fiels to make it easier the reading of files, config:
  - to remove pressures or resiliences easily
  - to change the input layers
- wrap the calculator into a multi-year capable script (with the data layers)
- make tests, other than `comparative/compare_scores.py`
- make repo public
- check the proabable R Bug Replication in cw.py

## TODO (more)

- Create Docker version for python implementation. 
- Create AWS Lambda version for python implementation
- Create Sphinx documentation
- Create User guides
- Github actions CI/CD