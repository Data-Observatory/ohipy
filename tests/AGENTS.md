# TEST SUITE KNOWLEDGE BASE

**Generated:** 2026-04-09

## OVERVIEW
pytest validation suite comparing Python OHI calculations against R reference via Docker. Tiered architecture: integrity (fast, no Docker) → parity → parity_full.

## STRUCTURE

```
tests/
├── conftest.py               # 3 markers: integrity, parity, parity_full; fixtures: config, layers, runner, fixture_config, fixture_layers, strict_layers
├── helpers/
│   ├── __init__.py
│   └── comparison.py          # Shared comparison module (compare_scores, format_failure_report, assert_parity)
├── test_r_parity.py          # Baseline parity (SINGLE SOURCE OF TRUTH)
├── test_parity_full.py        # 44 comprehensive parity tests
├── test_layer_audit.py       # Layer integrity gate (5 tests, @pytest.mark.integrity)
├── test_comparison_helper.py # Comparison helper unit tests (10 tests, @pytest.mark.integrity)
├── test_edge_cases.py        # Schema/type/range edge cases (7 tests, @pytest.mark.integrity)
├── test_runner_basic.py       # OHIRunner instantiation
├── test_overrides.py          # ConfigOverlay weight/disable tests
├── test_weight_sensitivity.py # Goal weight modification impacts
├── test_dimension_isolation.py # Pressure/resilience disable tests
├── test_multi_year.py         # Multi-year aggregation
├── comparative/
│   ├── compare_scores.py      # Comparison script (polars, tolerance: 0.01, uses helpers/comparison.py)
│   ├── calculate_scores.r     # R reference generator
│   ├── scores_2024_r.csv      # R fixture (IMMUTABLE)
│   └── cache/noise_*pct/      # Noisy layer caches
└── parity/
    ├── setup_fixtures.py      # Generates 44 R fixture files
    ├── r_runner.py            # Docker R executor with prereq checks
    └── data_modifiers.py      # Noise/weight/matrix modifications
```

## TEST CATEGORIES

### Layer Integrity (test_layer_audit.py)
5 tests validating all 98 declared layers in data/layers.csv:
- `test_all_declared_layers_exist`: Files exist in parquet/ or csv/
- `test_all_declared_layers_loadable`: load_layers() successfully loaded every declared layer
- `test_all_loaded_layers_nonempty`: Every loaded layer has at least one row
- `test_all_loaded_layers_have_data`: Layers have non-null values in value columns
- `test_no_duplicate_layer_keys`: Layer names are unique in layers.csv
Marked `@pytest.mark.integrity`.

### Comparison Helper Tests (test_comparison_helper.py)
10 unit tests for `tests/helpers/comparison.py`:
- Outer join missing-row detection (2 tests)
- Symmetric NaN handling: both-NaN passes, one-sided NaN fails (3 tests)
- Key uniqueness assertion before joining (1 test)
- Tolerance boundary: below passes, above fails (1 test)
- Rounding behavior: scores rounded to 2dp before comparison (1 test)
- Failure report formatting grouped by dimension then goal (1 test)
- assert_parity raises AssertionError with formatted report (1 test)
Marked `@pytest.mark.integrity`.

### Edge Case Tests (test_edge_cases.py)
7 tests for schema/type/range consistency between R and Python outputs:
- `test_region_id_type_consistency`: region_id is integer in both
- `test_goal_case_consistency`: All 18 goal codes match exactly (uppercase)
- `test_dimension_names_consistency`: Dimension names match (lowercase, no trailing spaces)
- `test_no_inf_values`: Neither output contains Inf or -Inf values
- `test_row_count_matches`: Overlapping key space matches between outputs
- `test_global_region_present`: region_id=0 exists for Index goal in both
- `test_score_range`: Non-NaN scores within valid range (0-100 for status/score/future/pressures/resilience, -1 to 1 for trend)
Marked `@pytest.mark.integrity`.

### Baseline R Parity (test_r_parity.py)
- Single test: Python scores vs R reference fixture
- Tolerance: 0.01 (updated from 0.05)
- Uses outer join via shared comparison helper (`tests/helpers/comparison.py`)
- On failure: detailed breakdown in scores_difference.csv
- Marked `@pytest.mark.parity`

### Comprehensive Parity (test_parity_full.py)
- 44 tests: 4 datasets × 11 variations
- Datasets: original, noise_1pct, noise_5pct, noise_10pct
- Variations: baseline, weight_* (4), pressure_* (3), resilience_* (3)
- Uses ConfigOverlay to apply modifications
- Tolerance: 0.01 (updated from 0.05)
- Uses shared comparison helper (`tests/helpers/comparison.py`)
- Skips if fixtures missing (auto-gen with OHI_AUTO_GENERATE_FIXTURES=1)
- Marked `@pytest.mark.parity_full`

### Unit Tests
- test_runner_basic.py: OHIRunner instantiation
- test_overrides.py: ConfigOverlay weight/disable
- test_weight_sensitivity.py: Goal weight modification impacts
- test_dimension_isolation.py: Pressure/resilience disable
- test_multi_year.py: Multi-year aggregation

## KEY COMMANDS

```bash
# Tiered execution (default: integrity + parity)
./tests/run_all_tests.sh                    # integrity + parity
./tests/run_all_tests.sh --tier integrity   # Fast, no Docker
./tests/run_all_tests.sh --tier parity      # Baseline R parity
./tests/run_all_tests.sh --tier parity_full # All 44 variations
./tests/run_all_tests.sh --all              # Everything

# Smoke test (no Docker, no fixtures)
./tests/run_all_tests.sh --skip-docker --no-fixtures

# Direct pytest markers
uv run pytest -m integrity -v    # Layer integrity, comparison helper, edge cases (22 tests)
uv run pytest -m parity -v        # Baseline R parity
uv run pytest -m parity_full -v  # All 44 variations

# R parity baseline
uv run pytest tests/test_r_parity.py -v

# Generate 44 fixtures
uv run python tests/parity/setup_fixtures.py
```

## CRITICAL CONSTRAINTS

- Shared comparison module: `tests/helpers/comparison.py` provides `compare_scores()`, `format_failure_report()`, `assert_parity()`
- Outer join (NOT inner) for all parity comparisons
- Symmetric NaN rule: both-NaN passes, one-sided NaN fails
- Key uniqueness assertion before joining
- Tolerance: 0.01 absolute in 0-100 score space
- `strict_layers` fixture in conftest.py hard-fails on missing declared layers
- Layer audit validates all 98 declared layers in data/layers.csv
- Dimension-first failure reporting
- scores_2024_r.csv is IMMUTABLE. The R reference fixture.
- Docker requires dplyr <= 1.0.10. Newer breaks group_by.
- 44 fixtures require Docker + chl/ repo to generate.
- compare_scores.py: Uses polars (was pandas), tolerance 0.01, uses shared comparison helper.