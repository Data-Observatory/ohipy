# OHI Python Test Suite

Testing framework for Ocean Health Index Python calculations.

## Quick Start

```bash
# Full test suite (recommended - handles all prerequisites)
./tests/run_all_tests.sh

# Smoke test (unit tests + base parity, no Docker)
./tests/run_all_tests.sh --skip-docker

# Unit tests only (no Docker or R fixtures needed)
uv run pytest tests/ -v

# Run baseline parity test
uv run pytest tests/test_r_parity.py -v

# Run 44 parity tests (requires R fixtures)
uv run pytest tests/test_parity_full.py -v
```

## Test Suite Orchestrator

**File**: `tests/run_all_tests.sh`

**What it does**: Full test pipeline that handles Docker image building, chl/ repo cloning, fixture generation, and pytest execution automatically.

**How to run**:
```bash
# Full pipeline with all checks (default)
./tests/run_all_tests.sh

# Skip Docker checks and fixture generation (use existing fixtures)
./tests/run_all_tests.sh --skip-docker

# Skip fixture generation (use existing)
./tests/run_all_tests.sh --no-fixtures

# Show help
./tests/run_all_tests.sh --help
```

**Pipeline phases**:
1. Preflight checks (uv, Docker, Docker image, chl repo)
2. Generate noisy layers (1%, 5%, 10%)
3. Generate R fixtures (44 combinations)
4. Generate Python scores
5. Run pytest with all tests

**Exit codes**:
- 0: All tests passed
- 1: One or more tests failed or preflight check failed

## Test Categories

### 1. R vs Python Baseline Parity

**File**: `tests/test_r_parity.py`

**What it tests**: Python output matches R reference fixture exactly.

**How to run**:
```bash
uv run pytest tests/test_r_parity.py -v
```

**Interpreting results**:

- **PASSED**: All Python scores match R scores within tolerance (0.05)
- **FAILED**: Differences written to `tests/comparative/scores_difference.csv`

**On failure**:
1. Check `tests/comparative/scores_difference.csv` for:
   - Which goals have differences
   - Which regions are affected
   - Score values from Python vs R
2. Run `uv run python tests/comparative/compare_scores.py` for detailed breakdown

### 2. Comprehensive Parity Tests (44 tests)

**File**: `tests/test_parity_full.py`

**What it tests**: Python vs R parity across 44 combinations (4 datasets × 11 variations).

| Test | Description | Count |
|------|-------------|-------|
| `test_parity_full` | Full parity suite | 44 |

**Datasets**:
- `original`: Uses `data/layers/csv/`
- `noise_1pct`: 1% Gaussian noise (seed=42)
- `noise_5pct`: 5% Gaussian noise (seed=42)
- `noise_10pct`: 10% Gaussian noise (seed=42)

**Variations** (11 per dataset):
- `baseline`: No modification
- `weight_fis_0.5`: FIS weight × 0.5
- `weight_fis_2.5_mar_1.5`: FIS × 2.5, MAR × 1.5
- `weight_fp_1.5`: FP × 1.5
- `weight_ao_0.5_tr_1.5`: AO × 0.5, TR × 1.5
- `pressure_cw_conquimica`: Remove cw_conquimica pressure
- `pressure_des_habitat_marino`: Remove des_habitat_marino pressure
- `pressure_both`: Remove both pressures
- `resilience_areas_mp`: Remove areas_mp resilience
- `resilience_cum_n_tratamiento`: Remove cum_n_tratamiento resilience
- `resilience_both`: Remove both resiliences

**How to run**:
```bash
# Generate R fixtures first (slow, ~30-60 min, requires Docker)
uv run python tests/parity/setup_fixtures.py

# Run all 44 tests
uv run pytest tests/test_parity_full.py -v
```

**Note**: Tests will **skip** if R fixtures are not present. The setup script generates fixtures that are compared against Python output.

### 3. Unit Tests

| File | What It Tests |
|------|---------------|
| `test_runner_basic.py` | OHIRunner instantiation |
| `test_overrides.py` | ConfigOverlay weight/disable overrides |
| `test_weight_sensitivity.py` | Goal weight modification impacts |
| `test_dimension_isolation.py` | Pressure/resilience disable operations |
| `test_multi_year.py` | Multi-year score aggregation |

## Test Structure

```
tests/
├── run_all_tests.sh           # Full test suite orchestrator
├── test_r_parity.py           # Baseline R vs Python parity
├── test_parity_full.py        # 44 comprehensive parity tests
├── test_*.py                  # Unit tests
├── comparative/                # R validation and comparison
│   ├── compare_scores.py      # Python vs R score comparison script
│   ├── calculate_scores.r      # R score calculation script
│   ├── scores_2024_r.csv       # R reference scores (fixture)
│   ├── scores_2024_py.csv      # Python calculated scores
│   ├── scores_difference.csv   # Difference report on test failure
│   ├── cache/                  # Cached noisy layers and fixtures
│   │   ├── noise_1pct_seed42/
│   │   ├── noise_5pct_seed42/
│   │   └── noise_10pct_seed42/
│   └── images/R/              # Docker image for R validation
├── parity/
│   ├── __init__.py
│   ├── data_modifiers.py      # Noise/weight/matrix modification utilities
│   ├── r_runner.py            # Docker R runner
│   └── setup_fixtures.py      # R fixture generation script
├── fixtures/                  # Test fixtures
└── conftest.py                # Pytest configuration
```

## Comparative Directory

The `tests/comparative/` directory contains R validation and comparison tools:

| File | Purpose |
|------|---------|
| `compare_scores.py` | Compare Python scores against R reference |
| `calculate_scores.r` | R script to generate reference scores |
| `scores_2024_r.csv` | R reference fixture (DO NOT MODIFY) |
| `scores_2024_py.csv` | Python-generated scores for comparison |
| `scores_difference.csv` | Detailed diff report (generated on test failure) |
| `cache/` | Cached noisy layer sets and R fixtures for 44 parity tests |

The R fixtures are generated using Docker with pinned dplyr <= 1.0.10 to ensure reproducibility.

## Prerequisites

- Python 3.13+
- `uv` package manager
- Project dependencies (`uv sync`)
- Docker (for R fixture generation)

## Setup for Comprehensive Parity Tests

The 44 parity tests require R fixtures generated from the R reference implementation:

```bash
# Check if fixtures exist
uv run python tests/parity/setup_fixtures.py --check

# Generate fixtures (slow, requires Docker)
uv run python tests/parity/setup_fixtures.py

# Force regenerate
uv run python tests/parity/setup_fixtures.py --overwrite

# Generate with parallel R processes
uv run python tests/parity/setup_fixtures.py --parallel 4
```

Alternatively, use the orchestrator script which handles all of this automatically:

```bash
./tests/run_all_tests.sh
```

## Adding New Parity Scenarios

To add a new parity scenario:

1. Create a modification function in `tests/parity/data_modifiers.py`
2. Add variation to `tests/parity/setup_fixtures.py`
3. Add test case in `tests/test_parity_full.py`
4. Run tests to verify: `uv run pytest tests/test_parity_full.py -v`
