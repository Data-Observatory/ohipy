# OHI Python Test Suite

Testing framework for Ocean Health Index Python calculations.

## Quick Start

```bash
# Run all tests (43 tests)
uv run pytest tests/ -v

# Run only baseline parity test
uv run pytest tests/test_r_parity.py -v

# Run all parity scenarios (14 tests)
uv run pytest tests/test_parity_scenarios.py -v
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

### 2. Parity Scenarios (Extended Testing)

**File**: `test_parity_scenarios.py`

**What it tests**: Python handles various data modifications correctly.

| Test | Description | Count |
|------|-------------|-------|
| `test_baseline_parity` | Matches R fixture | 1 |
| `test_noise_injection_runs` | Noisy layer data (1%, 5%, 10%) | 3 |
| `test_weight_modification_runs` | Modified goal weights | 4 |
| `test_pressure_removal_runs` | Removed pressures | 3 |
| `test_resilience_removal_runs` | Removed resilience | 3 |

**How to run**:
```bash
uv run pytest tests/test_parity_scenarios.py -v
```

**What these tests verify**:
- Python calculation runs without errors with modified data
- Scores are generated for all expected goals
- Data format is correct (region_id, goal, dimension, score columns)

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
├── test_parity_scenarios.py   # Extended parity scenarios
├── test_*.py                  # Unit tests
├── parity/
│   ├── __init__.py
│   ├── data_modifiers.py      # Noise/weight/matrix modification utilities
│   └── r_runner.py            # Docker R runner (for future use)
├── fixtures/                  # Test fixtures
└── conftest.py                # Pytest configuration
```

## Prerequisites

- Python 3.13+
- `uv` package manager
- Project dependencies (`uv sync`)

## Adding New Parity Scenarios

To add a new parity scenario:

1. Create a modification function in `tests/parity/data_modifiers.py`
2. Add a test case in `tests/test_parity_scenarios.py`
3. Run tests to verify: `uv run pytest tests/test_parity_scenarios.py -v`
