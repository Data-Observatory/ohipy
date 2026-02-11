# OHI Python Validation

## Setup

### Clone ohi core chl

At the root of the project:

```bash
git clone https://github.com/OHI-Science/chl
```

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
docker run --rm -v "$PWD":/home/project -w /home/project ohicore-r-env Rscript comparative/calculate_scores.r
```

This will create `comparative/scores_2024_r.csv`

### Run Python Implementation

At the root of the project, run (you need to install uv before):

```bash
uv sync
cd src
```

And then:

```bash
uv run python -c "from ohipy.config import load_config; from ohipy.layers import load_layers; from ohipy.calculate_all import calculate_all; scores = calculate_all(load_config(), load_layers(load_config())); scores.to_csv('../comparative/scores_2024_py.csv', index=False)"
```

That will generate the Python scores files at `comparative/scores_2024_py.csv`. To check if they match with R scores (at the root of the project):

```bash
cd ..
uv run python comparative/compare_scores.py
```

The comparison script outputs a SUCESS/FAILURE summary and writes `comparative/scores_difference.csv` with more details for the differences. This the single source of truth for pass/fail.

## TODO

- remove pandas groupby warning
- @discrepancy_report.md shows an error on the R implementation; we need to fix that in this implementation after validation from the ohi Chile team
- optimize and increase calculation speed
- fix execution paths (they change a lot now)
- modify config fiels to make it easier the reading of files, config:
  - to remove pressures or resiliences easily
  - to change the input layers
- wrap the calculator into a multi-year capable script (with the data layers)
- make tests, other than `comparative/compare_scores.py`
- make repo public

## TODO (more)

- Create Docker version for python implementation. 
- Create AWS Lambda version for python implementation
- Create Sphinx documentation
- Create User guides
- Github actions CI/CD