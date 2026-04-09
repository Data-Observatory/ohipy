# TEST SUITE KNOWLEDGE BASE

**Generated:** 2026-04-08

## OVERVIEW
pytest validation suite comparing Python OHI calculations against R reference via Docker.

## STRUCTURE

```
tests/
├── conftest.py               # 5 fixtures: config, layers, runner, fixture_config, fixture_layers
├── test_r_parity.py          # Baseline parity (SINGLE SOURCE OF TRUTH)
├── test_parity_full.py        # 44 comprehensive parity tests
├── test_runner_basic.py       # OHIRunner instantiation
├── test_overrides.py          # ConfigOverlay weight/disable tests
├── test_weight_sensitivity.py # Goal weight modification impacts
├── test_dimension_isolation.py # Pressure/resilience disable tests
├── test_multi_year.py         # Multi-year aggregation
├── comparative/
│   ├── compare_scores.py      # Main comparison script (tolerance: 0.05)
│   ├── calculate_scores.r     # R reference generator
│   ├── scores_2024_r.csv      # R fixture (IMMUTABLE)
│   └── cache/noise_*pct/      # Noisy layer caches
└── parity/
    ├── setup_fixtures.py      # Generates 44 R fixture files
    ├── r_runner.py            # Docker R executor with prereq checks
    └── data_modifiers.py      # Noise/weight/matrix modifications
```

## TEST CATEGORIES

### Baseline R Parity (test_r_parity.py)
- Single test: Python scores vs R reference fixture
- Tolerance: 0.05
- On failure: detailed breakdown in scores_difference.csv

### Comprehensive Parity (test_parity_full.py)
- 44 tests: 4 datasets × 11 variations
- Datasets: original, noise_1pct, noise_5pct, noise_10pct
- Variations: baseline, weight_* (4), pressure_* (3), resilience_* (3)
- Uses ConfigOverlay to apply modifications
- Skips if fixtures missing (auto-gen with OHI_AUTO_GENERATE_FIXTURES=1)

### Unit Tests
- test_runner_basic.py: OHIRunner instantiation
- test_overrides.py: ConfigOverlay weight/disable
- test_weight_sensitivity.py: Goal weight modification impacts
- test_dimension_isolation.py: Pressure/resilience disable
- test_multi_year.py: Multi-year aggregation

## KEY COMMANDS

```bash
# Full test suite
./tests/run_all_tests.sh

# Smoke test (no Docker, no fixtures)
./tests/run_all_tests.sh --skip-docker --no-fixtures

# Unit tests only
uv run pytest tests/ -v

# R parity baseline
uv run pytest tests/test_r_parity.py -v

# Generate 44 fixtures
uv run python tests/parity/setup_fixtures.py
```

## CRITICAL CONSTRAINTS

- scores_2024_r.csv is IMMUTABLE. The R reference fixture.
- Docker requires dplyr <= 1.0.10. Newer breaks group_by.
- 44 fixtures require Docker + chl/ repo to generate.
- compare_scores.py: R local == R remote, then Python == R (tolerance 0.05).