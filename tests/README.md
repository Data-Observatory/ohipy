# OHI Python Test Suite

Comprehensive testing framework for Ocean Health Index Python calculations.

## Directory Structure

```
tests/
├── conftest.py              # Pytest fixtures (config, layers, runner)
├── fixtures/                # Test data and configurations
│   ├── config.yaml          # Minimal test config
│   ├── conf/                # Test configuration CSVs
│   ├── layers/              # Minimal layer data for fast tests
│   └── test_data/           # Full test data (R + Python shared)
├── integration/             # Integration tests (R vs Python parity)
│   └── test_noise_parity.py # Noise injection + R comparison
├── noise/                   # Noise injection utilities
│   └── generator.py         # NoiseGenerator class
├── output/                  # Test output files (gitignored)
├── scripts/                 # Test utility scripts
│   ├── setup_test_data.py   # Copy data from chl/ and data/
│   └── run_integration_tests.py
├── test_dimension_isolation.py  # Pressure/resilience tests
├── test_multi_year.py       # Multi-year aggregation tests
├── test_overrides.py        # ConfigOverlay tests
├── test_r_parity.py         # R vs Python baseline parity
├── test_runner_basic.py     # OHIRunner basic tests
└── test_weight_sensitivity.py   # Goal weight modification tests
```

## Quick Start

### Unit Tests (No Docker Required)

```bash
# Run all unit tests
make test-quick

# Or directly with pytest
uv run pytest tests/ -v --ignore=tests/integration/
```

### Integration Tests (Requires Docker)

Integration tests compare Python scores against R reference implementation.

```bash
# Setup test data (one-time or after data changes)
make test-data

# Run integration tests
make test-integration
```

## Makefile Targets

| Target | Command | Description |
|--------|---------|-------------|
| `make test-data` | `uv run python tests/scripts/setup_test_data.py --force` | Copy test data from `chl/` and `data/` to `tests/fixtures/test_data/` |
| `make test-quick` | `uv run pytest tests/ -v --ignore=tests/integration/` | Run unit tests (no Docker needed) |
| `make test-integration` | `uv run python tests/scripts/run_integration_tests.py --setup` | Run R vs Python parity tests (requires Docker) |
| `make test-all` | `test-quick` + `test-integration` | Run all tests |
| `make help` | — | Show available targets |

## Prerequisites

### For Unit Tests

- Python 3.13+
- `uv` package manager
- Project dependencies (`uv sync`)

### For Integration Tests

- Everything above, plus:
- Docker installed and running
- `ohicore-r-env` Docker image built (see `comparative/images/R/`)
- `chl/` repository cloned (for R files)

## Test Categories

### 1. Unit Tests

Fast tests that don't require external dependencies.

| File | What It Tests |
|------|---------------|
| `test_runner_basic.py` | OHIRunner instantiation and basic methods |
| `test_overrides.py` | ConfigOverlay weight and disable overrides |
| `test_weight_sensitivity.py` | Goal weight modification impacts |
| `test_dimension_isolation.py` | Pressure/resilience disable operations |
| `test_multi_year.py` | Multi-year score aggregation |

### 2. Integration Tests

Tests that require Docker and compare against R implementation.

| File | What It Tests |
|------|---------------|
| `test_r_parity.py` | Baseline Python vs R score comparison |
| `test_noise_parity.py` | Python vs R with noise injection |

### 3. Noise Testing

The `tests/noise/generator.py` module provides `NoiseGenerator` class for robustness testing:

```python
from tests.noise.generator import NoiseGenerator

gen = NoiseGenerator(seed=42)  # Reproducible!

# Gaussian noise (5% of std dev)
noisy_df = gen.inject_gaussian(df, sigma_pct=0.05)

# Bootstrap resampling (80% of rows)
resampled_df = gen.bootstrap_resample(df, frac=0.8)

# Dropout (10% values → NaN)
sparse_df = gen.inject_dropout(df, rate=0.1)

# Apply to entire directory
gen.apply_to_directory(
    "tests/fixtures/test_data/layers",
    "tests/fixtures/test_data/layers_noisy",
    method="gaussian",
    sigma_pct=0.05
)
```

## Fixtures

Available pytest fixtures from `conftest.py`:

| Fixture | Description |
|---------|-------------|
| `config` | Default OHI configuration dict |
| `layers` | Default OHI layers dict |
| `runner` | OHIRunner instance |
| `fixture_config` | Minimal test configuration |
| `fixture_layers` | Minimal test layers |

Usage in tests:

```python
def test_something(runner, config, layers):
    scores = runner.run(year=2024, layers=layers["data"])
    assert scores is not None
```

## Test Data Setup

The `tests/scripts/setup_test_data.py` script copies files to `tests/fixtures/test_data/`:

```bash
# Full setup (includes R files from chl/)
uv run python tests/scripts/setup_test_data.py --force

# Skip R files (if chl/ not available)
uv run python tests/scripts/setup_test_data.py --skip-r --force
```

**What gets copied:**
- `config.R`, `functions.R` from `chl/comunas/conf/` (R-specific)
- `goals.csv`, `pressures_matrix.csv`, etc. from `data/conf/`
- All layer CSVs from `data/layers/csv/`
- `layers.csv` from `data/`
- Generates `config.yaml` for Python

## Running Specific Tests

```bash
# Single test file
uv run pytest tests/test_weight_sensitivity.py -v

# Single test function
uv run pytest tests/test_dimension_isolation.py::test_disable_single_pressure -v

# With coverage
uv run pytest tests/ --cov=src/ohipy --cov-report=html

# Parallel execution
uv run pytest tests/ -n auto --ignore=tests/integration/
```

## Troubleshooting

### "test_data not set up"
Run: `make test-data`

### "Docker not available"
Integration tests skip automatically if Docker isn't running. Run `make test-quick` for unit tests only.

### "chl/ directory not found"
Clone the R reference repository:
```bash
git clone https://github.com/OHI-Science/chl
```

### "ohicore-r-env image not found"
Build the Docker image:
```bash
cd comparative/images/R
docker build -t ohicore-r-env .
```
