# OHI Python Test Suite

Testing framework for Ocean Health Index Python calculations.

## Quick Start

```bash
# Run all tests
uv run pytest tests/ -v

# Run baseline parity test
uv run pytest tests/test_r_parity.py -v

# Run 44 parity tests (requires R fixtures)
uv run pytest tests/test_parity_full.py -v
```

## Test Categories

### 1. R vs Python Baseline Parity

**File**: `test_r_parity.py`

**What it tests**: Python output matches R reference fixture exactly.

**How to run**:
```bash
uv run pytest tests/test_r_parity.py -v
```

**Interpreting results**:

- **PASSED**: All Python scores match R scores within tolerance (0.05)
- **FAILED**: Differences written to `comparative/scores_difference.csv`

**On failure**:
1. Check `comparative/scores_difference.csv` for:
   - Which goals have differences
   - Which regions are affected
   - Score values from Python vs R
2. Run `uv run python comparative/compare_scores.py` for detailed breakdown

### 2. Comprehensive Parity Tests (44 tests)

**File**: `test_parity_full.py`

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
├── test_r_parity.py           # Baseline R vs Python parity
├── test_parity_full.py        # 44 comprehensive parity tests
├── test_*.py                  # Unit tests
├── parity/
│   ├── __init__.py
│   ├── data_modifiers.py      # Noise/weight/matrix modification utilities
│   ├── r_runner.py            # Docker R runner
│   └── setup_fixtures.py      # R fixture generation script
├── fixtures/                  # Test fixtures
└── conftest.py                # Pytest configuration
```

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

## Adding New Parity Scenarios

To add a new parity scenario:

1. Create a modification function in `tests/parity/data_modifiers.py`
2. Add variation to `tests/parity/setup_fixtures.py`
3. Add test case in `tests/test_parity_full.py`
4. Run tests to verify: `uv run pytest tests/test_parity_full.py -v`
