# Comprehensive Testing Framework for OHI Python

## TL;DR

> **Quick Summary**: Create a unified testing framework with noise injection, R parity validation, and config override testing. Single test data directory (`tests/fixtures/test_data/`) shared by both Python and R, with setup script to copy from source directories.
>
> **Deliverables**:
> - Test data directory with R + Python shared files
> - Setup script to populate test data from `chl/` and `data/`
> - Noise injection framework with Gaussian and bootstrap methods
> - R vs Python parity tests with noisy data
> - Extended config override tests (weight sensitivity, pressure/resilience isolation)
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Setup → Noise Framework → Integration Tests

---

## Context

### Original Request
User wants comprehensive testing framework to:
1. Test robustness by injecting noise into data and comparing R vs Python results
2. Test config overrides (goal weights, pressure/resilience removal)
3. Use same data directory for both R and Python testing

### Key Constraints
- **Cannot modify `chl/` folder** - it's official/reference only
- **`chl/` may not always be present** - test data must be self-contained after setup
- **`functions.R` comes from `chl/`** - always copy, never modify
- **Use copies, not symlinks** - works without `chl/` and on all platforms
- **Skip R comparison for override tests** - R doesn't have ConfigOverlay system

### Current State
| Component | Status |
|-----------|--------|
| Basic R parity | `comparative/compare_scores.py` (single fixture) |
| Override tests | `tests/test_overrides.py` (3 tests) |
| Test fixtures | `tests/fixtures/` (minimal, Python-only) |
| Noise testing | **Does not exist** |
| Goal/dimension unit tests | **Does not exist** |

### Technical Decisions
1. **Single test data directory**: `tests/fixtures/test_data/` - both R and Python read from here
2. **Setup script**: Copies from `chl/comunas/conf/` (R-specific) and `data/` (shared)
3. **Noise injection**: Modifies `test_data/layers/` only, both systems see same noisy data
4. **Test isolation**: Test data is independent, can be regenerated anytime

---

## Work Objectives

### Core Objective
Create a comprehensive testing framework that validates Python implementation against R under various conditions (noisy data, config modifications).

### Concrete Deliverables
- `tests/fixtures/test_data/` directory structure
- `tests/scripts/setup_test_data.py` - setup script
- `tests/noise/` - noise injection module
- `tests/integration/test_noise_parity.py` - R vs Python with noise
- Extended tests in `tests/test_overrides.py` or new files

### Definition of Done
- [ ] Can run `uv run python tests/scripts/setup_test_data.py` to create test data
- [ ] Can run R calculation against `tests/fixtures/test_data/`
- [ ] Can run Python calculation against `tests/fixtures/test_data/`
- [ ] Noise injection produces measurable differences in scores
- [ ] R vs Python comparison works with noisy data
- [ ] Override tests validate weight sensitivity and P/R isolation

### Must Have
- Setup script that copies from `chl/` and `data/`
- Noise injection with at least Gaussian method
- R vs Python parity test that uses test_data directory
- Weight sensitivity test
- Pressure isolation test

### Must NOT Have (Guardrails)
- **DO NOT** modify `chl/` directory
- **DO NOT** modify `functions.R` after copying
- **DO NOT** create symlinks (use copies)
- **DO NOT** require `chl/` to be present at test time (only at setup)
- **DO NOT** compare R vs Python for override tests (R has no ConfigOverlay)

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest in `tests/`)
- **Automated tests**: YES (TDD approach for new modules)
- **Framework**: pytest
- **Agent-Executed QA**: YES - verify each component works

### QA Policy
Every task includes agent-executed QA scenarios:
- **File operations**: Use Bash (ls, diff, wc)
- **Python modules**: Use Bash (uv run python -c, uv run pytest)
- **R calculation**: Use Bash (docker run)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - sequential, creates structure):
├── Task 1: Create test_data directory structure [quick]
├── Task 2: Create setup_test_data.py script [quick]
└── Task 3: Create R test calculation script [quick]

Wave 2 (Core Framework - parallel after Wave 1):
├── Task 4: Create noise generator module [unspecified-high]
├── Task 5: Create noise parity test [unspecified-high]
├── Task 6: Create weight sensitivity test [quick]
└── Task 7: Create pressure/resilience isolation tests [quick]

Wave 3 (Integration & Documentation - parallel after Wave 2):
├── Task 8: Create integration test runner [unspecified-high]
├── Task 9: Update test documentation [writing]
└── Task 10: Create Makefile targets [quick]
```

### Dependency Matrix
- **1-3**: No dependencies (foundation)
- **4**: Depends on 2 (needs test_data structure)
- **5**: Depends on 3, 4 (needs R script and noise generator)
- **6-7**: Depends on 2 (needs test_data structure)
- **8**: Depends on 5, 6, 7 (needs all tests working)
- **9-10**: Depends on 8 (needs integration working)

### Agent Dispatch Summary
- **Wave 1**: quick (3 tasks)
- **Wave 2**: 2x unspecified-high + 2x quick
- **Wave 3**: unspecified-high + writing + quick

---

## TODOs

---

## Wave 1: Foundation

- [x] 1. Create test_data directory structure

  **What to do**:
  - Create `tests/fixtures/test_data/` directory
  - Create subdirectories: `conf/`, `layers/`
  - Create `tests/noise/` directory with `__init__.py`
  - Create `tests/integration/` directory with `__init__.py`
  - Create `tests/scripts/` directory if not exists
  - Create `tests/output/` directory for R/Python test outputs

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (foundation for other tasks)
  - **Parallel Group**: Wave 1 (sequential with Task 2, 3)
  - **Blocks**: Tasks 4-10
  - **Blocked By**: None

  **References**:
  - `tests/fixtures/` - existing fixture structure to follow
  - `data/conf/` - structure to replicate
  - `chl/comunas/conf/` - R-specific files to know about

  **Acceptance Criteria**:
  - [ ] `tests/fixtures/test_data/conf/` exists
  - [ ] `tests/fixtures/test_data/layers/` exists
  - [ ] `tests/noise/__init__.py` exists
  - [ ] `tests/integration/__init__.py` exists
  - [ ] `tests/scripts/` exists
  - [ ] `tests/output/` exists (for R/Python test outputs)

  **QA Scenarios**:
  ```
  Scenario: Directory structure created correctly
    Tool: Bash
    Steps:
      1. ls -la tests/fixtures/test_data/
      2. ls -la tests/noise/
      3. ls -la tests/integration/
    Expected Result: All directories exist with correct subdirectories
    Evidence: .sisyphus/evidence/task-1-structure.txt
  ```

  **Commit**: NO (groups with Task 2, 3)

---

- [x] 2. Create setup_test_data.py script

  **What to do**:
  - Create `tests/scripts/setup_test_data.py`
  - Copy `config.R` from `chl/comunas/conf/` to `test_data/conf/`
  - Copy `functions.R` from `chl/comunas/conf/` to `test_data/conf/`
  - Copy all CSVs from `data/conf/` to `test_data/conf/`
  - Copy all CSVs from `data/layers/csv/` to `test_data/layers/`
  - Copy `data/layers.csv` to `test_data/`
  - Create `test_data/config.yaml` for Python (pointing to test_data paths)
  - Add `--skip-r` flag to skip R-specific files if `chl/` not present
  - Add `--force` flag to overwrite existing files
  - Print summary of what was copied

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential in Wave 1)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 4-8
  - **Blocked By**: Task 1

  **References**:
  - `chl/comunas/conf/config.R` - R config file (50 lines)
  - `chl/comunas/conf/functions.R` - R goal functions (1366 lines)
  - `data/conf/` - shared config CSVs
  - `data/layers/csv/` - layer data files
  - `data/layers.csv` - layer metadata
  - `src/ohipy/config/__init__.py` - how Python loads config
  - `comparative/calculate_scores.r` - existing R script to base on

  **Acceptance Criteria**:
  - [ ] Script runs: `uv run python tests/scripts/setup_test_data.py`
  - [ ] With `chl/` present: copies `config.R` and `functions.R`
  - [ ] With `--skip-r` or no `chl/`: skips R files gracefully
  - [ ] All CSVs from `data/conf/` are copied
  - [ ] All layer files from `data/layers/csv/` are copied
  - [ ] `test_data/config.yaml` points to `test_data/` paths
  - [ ] Script prints summary of files copied

  **QA Scenarios**:
  ```
  Scenario: Setup script copies all files correctly
    Tool: Bash
    Preconditions: chl/ directory exists
    Steps:
      1. uv run python tests/scripts/setup_test_data.py --force
      2. ls tests/fixtures/test_data/conf/ | wc -l
      3. ls tests/fixtures/test_data/layers/ | wc -l
      4. diff tests/fixtures/test_data/conf/goals.csv data/conf/goals.csv
    Expected Result: Files copied, diff shows no differences
    Evidence: .sisyphus/evidence/task-2-setup.txt

  Scenario: Setup script handles missing chl/ gracefully
    Tool: Bash
    Preconditions: Temporarily rename chl/ to chl_backup/
    Steps:
      1. uv run python tests/scripts/setup_test_data.py --skip-r --force
      2. Check exit code is 0
      3. Check R files do not exist in test_data/conf/
    Expected Result: Script completes, R files skipped
    Evidence: .sisyphus/evidence/task-2-skip-r.txt
  ```

  **Commit**: NO (groups with Task 1, 3)

---

- [x] 3. Create R test calculation script

  **What to do**:
  - Create `tests/fixtures/test_data/calculate_test.r`
  - Similar to `comparative/calculate_scores.r` but points to `test_data/` directory
  - Uses relative paths from script location
  - Outputs to `tests/output/scores_r_test.csv`
  - Ensure script works when run from project root via Docker

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential in Wave 1)
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 5
  - **Blocked By**: None (just needs to know directory structure)

  **References**:
  - `comparative/calculate_scores.r` - existing R script to base on
  - `chl/comunas/calculate_scores.r` - original R script structure
  - Key pattern: `setwd()` to scenario dir, then `ohicore::Conf("conf")`

  **Acceptance Criteria**:
  - [ ] File created at `tests/fixtures/test_data/calculate_test.r`
  - [ ] Script sets working directory to `tests/fixtures/test_data/`
  - [ ] Script loads config via `ohicore::Conf("conf")`
  - [ ] Script loads layers via `ohicore::Layers("layers.csv", "layers")`
  - [ ] Script creates `tests/output/` directory if it doesn't exist
  - [ ] Script outputs to `tests/output/scores_r_test.csv`
  - [ ] Can run via: `docker run ... Rscript tests/fixtures/test_data/calculate_test.r`

  **QA Scenarios**:
  ```
  Scenario: R test script runs in Docker
    Tool: Bash
    Preconditions: Docker available, ohicore-r-env image exists, setup_test_data.py run
    Steps:
      1. docker run --rm -v "$PWD":/home/project -w /home/project ohicore-r-env Rscript tests/fixtures/test_data/calculate_test.r
      2. ls tests/output/scores_r_test.csv
      3. wc -l tests/output/scores_r_test.csv
    Expected Result: R script produces scores file with expected row count
    Evidence: .sisyphus/evidence/task-3-r-script.txt
  ```

  **Commit**: YES
  - Message: `test: add test_data directory structure and setup scripts`
  - Files: `tests/fixtures/test_data/`, `tests/scripts/setup_test_data.py`, `tests/noise/__init__.py`, `tests/integration/__init__.py`
  - Pre-commit: `uv run python tests/scripts/setup_test_data.py --skip-r`

---

## Wave 2: Core Framework

- [x] 4. Create noise generator module

  **What to do**:
  - Create `tests/noise/generator.py` with `NoiseGenerator` class
  - Implement `inject_gaussian(df, columns, sigma_pct)` - adds Gaussian noise
  - Implement `bootstrap_resample(df, frac, seed)` - samples rows with replacement
  - Implement `inject_dropout(df, columns, rate)` - sets random values to NaN
  - Implement `apply_to_directory(layers_dir, output_dir, method, **kwargs)` - applies noise to all layer files
  - Support seed parameter for reproducibility
  - Preserve file structure and non-numeric columns

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7)
  - **Blocks**: Task 5
  - **Blocked By**: Task 2

  **References**:
  - `data/layers/csv/fis_b_bmsy_chl2024.csv` - example layer with rgn_id, year, value columns
  - `src/ohipy/layers/__init__.py` - how layers are loaded
  - Use pandas for DataFrame manipulation
  - Use numpy for random number generation

  **Acceptance Criteria**:
  - [ ] `NoiseGenerator` class with seed parameter
  - [ ] `inject_gaussian()` modifies numeric columns with Gaussian noise
  - [ ] `bootstrap_resample()` samples rows with replacement
  - [ ] `inject_dropout()` sets random values to NaN
  - [ ] `apply_to_directory()` processes all CSV files in a directory
  - [ ] All methods preserve non-numeric columns
  - [ ] Seed parameter ensures reproducibility

  **QA Scenarios**:
  ```
  Scenario: Gaussian noise injection works
    Tool: Bash
    Steps:
      1. uv run python -c "
         from tests.noise.generator import NoiseGenerator
         import pandas as pd
         df = pd.DataFrame({'rgn_id': [1,2,3], 'value': [0.5, 0.6, 0.7]})
         gen = NoiseGenerator(seed=42)
         noisy = gen.inject_gaussian(df, ['value'], sigma_pct=0.1)
         print(noisy)
         assert noisy['value'].std() != df['value'].std()
         print('OK')
         "
    Expected Result: Noisy values differ from original, seed produces same result
    Evidence: .sisyphus/evidence/task-4-gaussian.txt

  Scenario: Bootstrap resampling works
    Tool: Bash
    Steps:
      1. uv run python -c "
         from tests.noise.generator import NoiseGenerator
         import pandas as pd
         df = pd.DataFrame({'rgn_id': range(10), 'value': range(10)})
         gen = NoiseGenerator(seed=42)
         resampled = gen.bootstrap_resample(df, frac=0.8)
         print(f'Original: {len(df)}, Resampled: {len(resampled)}')
         assert len(resampled) == int(len(df) * 0.8)
         print('OK')
         "
    Expected Result: Resampled dataframe has correct size, may have duplicates
    Evidence: .sisyphus/evidence/task-4-bootstrap.txt

  Scenario: Apply to directory works
    Tool: Bash
    Preconditions: setup_test_data.py run
    Steps:
      1. uv run python -c "
         from tests.noise.generator import NoiseGenerator
         gen = NoiseGenerator(seed=42)
         gen.apply_to_directory(
             'tests/fixtures/test_data/layers',
             'tests/fixtures/test_data/layers_noisy',
             method='gaussian',
             sigma_pct=0.05
         )
         print('OK')
         "
      2. ls tests/fixtures/test_data/layers_noisy/ | wc -l
    Expected Result: Noisy directory created with same number of files
    Evidence: .sisyphus/evidence/task-4-directory.txt
  ```

  **Commit**: NO (groups with Wave 2)

---

- [x] 5. Create noise parity test

  **What to do**:
  - Create `tests/integration/test_noise_parity.py`
  - Test: baseline parity (no noise) - Python vs R match within tolerance
  - Test: Gaussian noise parity - same noise applied, Python vs R match
  - Test: Bootstrap parity - same resample applied, Python vs R match
  - Parametrize by noise level (0%, 1%, 5%, 10%)
  - Skip test if Docker not available or `test_data/` not set up
  - Use `tests/output/` for generated scores
  - Compare using same logic as `comparative/compare_scores.py`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 6, 7)
  - **Blocks**: Task 8
  - **Blocked By**: Task 3, Task 4

  **References**:
  - `comparative/compare_scores.py` - existing comparison logic
  - `tests/test_r_parity.py` - existing R parity test pattern
  - `tests/noise/generator.py` - noise generator from Task 4
  - `tests/fixtures/test_data/calculate_test.r` - R script from Task 3

  **Acceptance Criteria**:
  - [ ] Test file created at `tests/integration/test_noise_parity.py`
  - [ ] `test_baseline_parity()` - no noise, Python vs R match
  - [ ] `test_gaussian_noise_parity(sigma_pct)` - parametrized
  - [ ] `test_bootstrap_parity(frac)` - parametrized
  - [ ] Tests skip if Docker unavailable
  - [ ] Tests skip if `test_data/` not set up
  - [ ] Comparison uses tolerance = 0.05

  **QA Scenarios**:
  ```
  Scenario: Baseline parity test passes
    Tool: Bash
    Preconditions: Docker available, test_data set up
    Steps:
      1. uv run pytest tests/integration/test_noise_parity.py::test_baseline_parity -v
    Expected Result: Test passes, Python and R scores match within tolerance
    Evidence: .sisyphus/evidence/task-5-baseline.txt

  Scenario: Gaussian noise test runs
    Tool: Bash
    Preconditions: Docker available, test_data set up
    Steps:
      1. uv run pytest tests/integration/test_noise_parity.py::test_gaussian_noise_parity -v -k "sigma_pct-0.01"
    Expected Result: Test runs (may have larger differences due to noise)
    Evidence: .sisyphus/evidence/task-5-gaussian.txt
  ```

  **Commit**: NO (groups with Wave 2)

---

- [x] 6. Create weight sensitivity test

  **What to do**:
  - Create `tests/test_weight_sensitivity.py` or extend `tests/test_overrides.py`
  - Test: modify single goal weight, verify index score changes
  - Test: zero weight for goal, verify goal excluded from index
  - Test: weight normalization (weights sum to 1)
  - Test: multiple weight variations for key goals (FIS, MAR, FP, AO)
  - Measure and report impact magnitude

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 7)
  - **Blocks**: Task 8
  - **Blocked By**: Task 2

  **References**:
  - `tests/test_overrides.py` - existing override test patterns
  - `src/ohipy/config_overlay.py` - ConfigOverlay.apply_weights()
  - `src/ohipy/runner.py` - OHIRunner with overrides parameter

  **Acceptance Criteria**:
  - [ ] Test file created or extended
  - [ ] `test_single_weight_change()` - weight change affects index
  - [ ] `test_zero_weight_excludes_goal()` - zero weight excludes goal
  - [ ] `test_weight_normalization()` - weights normalized to sum=1
  - [ ] `test_key_goals_weight_sensitivity()` - parametrized for FIS, MAR, FP, AO

  **QA Scenarios**:
  ```
  Scenario: Weight sensitivity tests pass
    Tool: Bash
    Steps:
      1. uv run pytest tests/test_weight_sensitivity.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-6-weights.txt
  ```

  **Commit**: NO (groups with Wave 2)

---

- [x] 7. Create pressure/resilience isolation tests

  **What to do**:
  - Create `tests/test_dimension_isolation.py`
  - Test: disable single pressure, verify pressure score changes
  - Test: disable all pressures for a goal, verify score calculation
  - Test: disable single resilience, verify resilience score changes
  - Test: disable all resiliences for a goal, verify score calculation
  - Verify no crashes with empty pressure/resilience matrices

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 6)
  - **Blocks**: Task 8
  - **Blocked By**: Task 2

  **References**:
  - `tests/test_overrides.py` - existing override test patterns
  - `src/ohipy/config_overlay.py` - ConfigOverlay.apply_disable()
  - `data/conf/pressures_matrix.csv` - see available pressure columns
  - `data/conf/resilience_matrix.csv` - see available resilience columns

  **Acceptance Criteria**:
  - [ ] Test file created at `tests/test_dimension_isolation.py`
  - [ ] `test_disable_single_pressure()` - single pressure disabled
  - [ ] `test_disable_all_pressures_for_goal()` - all pressures for goal disabled
  - [ ] `test_disable_single_resilience()` - single resilience disabled
  - [ ] `test_disable_all_resiliences_for_goal()` - all resiliences for goal disabled
  - [ ] `test_empty_pressure_matrix()` - no crash with empty matrix

  **QA Scenarios**:
  ```
  Scenario: Dimension isolation tests pass
    Tool: Bash
    Steps:
      1. uv run pytest tests/test_dimension_isolation.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-7-isolation.txt
  ```

  **Commit**: YES
  - Message: `test: add noise injection framework and extended override tests`
  - Files: `tests/noise/generator.py`, `tests/integration/test_noise_parity.py`, `tests/test_weight_sensitivity.py`, `tests/test_dimension_isolation.py`
  - Pre-commit: `uv run pytest tests/`

---

## Wave 3: Integration & Documentation

- [x] 8. Create integration test runner

  **What to do**:
  - Create `tests/scripts/run_integration_tests.py`
  - Orchestrates: setup → noise injection → R run → Python run → compare
  - Supports multiple noise scenarios in one run
  - Generates summary report with all comparison results
  - Exit code reflects pass/fail
  - Can run specific scenarios via CLI args

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 9, 10)
  - **Blocks**: None
  - **Blocked By**: Tasks 5, 6, 7

  **References**:
  - `tests/scripts/setup_test_data.py` - setup script
  - `tests/noise/generator.py` - noise generator
  - `tests/integration/test_noise_parity.py` - individual test logic

  **Acceptance Criteria**:
  - [ ] Script created at `tests/scripts/run_integration_tests.py`
  - [ ] `--setup` flag runs setup first
  - [ ] `--noise-levels` arg accepts comma-separated values (e.g., "0,0.01,0.05")
  - [ ] `--output-dir` arg for results location
  - [ ] Generates JSON summary report
  - [ ] Exit code 0 if all pass, 1 if any fail

  **QA Scenarios**:
  ```
  Scenario: Integration runner executes full workflow
    Tool: Bash
    Preconditions: Docker available, chl/ present
    Steps:
      1. uv run python tests/scripts/run_integration_tests.py --setup --noise-levels 0,0.01
      2. cat tests/output/integration_summary.json
    Expected Result: Summary shows results for both noise levels
    Evidence: .sisyphus/evidence/task-8-runner.txt
  ```

  **Commit**: NO (groups with Wave 3)

---

- [x] 9. Update test documentation

  **What to do**:
  - Update `README.md` with testing section
  - Document how to run setup script
  - Document how to run integration tests
  - Document prerequisites (Docker, chl/ clone)
  - Add section to `tests/README.md` or create it
  - Document noise levels and their meaning

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 8, 10)
  - **Blocks**: None
  - **Blocked By**: Tasks 5, 6, 7

  **References**:
  - `README.md` - existing documentation
  - `tests/scripts/setup_test_data.py` - setup script to document
  - `tests/scripts/run_integration_tests.py` - runner to document

  **Acceptance Criteria**:
  - [ ] README.md has "Testing" section
  - [ ] Setup instructions documented
  - [ ] Integration test instructions documented
  - [ ] Prerequisites clearly listed
  - [ ] `tests/README.md` created or updated

  **QA Scenarios**:
  ```
  Scenario: Documentation is accurate - setup instructions
    Tool: Bash
    Steps:
      1. uv run python tests/scripts/setup_test_data.py --skip-r --force
      2. ls tests/fixtures/test_data/conf/config.R tests/fixtures/test_data/conf/functions.R
    Expected Result: R-specific files copied, test_data structure complete
    Evidence: .sisyphus/evidence/task-9-docs-setup.txt

  Scenario: Documentation is accurate - test-quick target
    Tool: Bash
    Steps:
      1. make test-quick
    Expected Result: Unit tests pass without Docker, output shows pass/fail counts
    Evidence: .sisyphus/evidence/task-9-docs-test-quick.txt

  Scenario: Documentation is accurate - test-integration target (requires Docker)
    Tool: Bash
    Steps:
      1. make test-integration 2>&1 | head -20
    Expected Result: Integration tests run, first 20 lines of output visible
    Evidence: .sisyphus/evidence/task-9-docs-test-integration.txt
  ```

  **Commit**: NO (groups with Wave 3)

---

- [x] 10. Create Makefile targets

  **What to do**:
  - Create `Makefile` or add to existing
  - `make test-data` - runs setup script
  - `make test-integration` - runs integration tests
  - `make test-all` - runs all tests including integration
  - `make test-quick` - runs only unit tests (no Docker needed)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 8, 9)
  - **Blocks**: None
  - **Blocked By**: Tasks 8, 9

  **References**:
  - Common Makefile patterns for Python projects
  - `tests/scripts/setup_test_data.py` - command to wrap
  - `tests/scripts/run_integration_tests.py` - command to wrap

  **Acceptance Criteria**:
  - [ ] `make test-data` runs setup script
  - [ ] `make test-integration` runs integration tests
  - [ ] `make test-all` runs all tests
  - [ ] `make test-quick` runs unit tests only
  - [ ] Makefile has proper .PHONY declarations

  **QA Scenarios**:
  ```
  Scenario: Makefile targets work
    Tool: Bash
    Steps:
      1. make test-quick
      2. make test-data
    Expected Result: Both commands execute successfully
    Evidence: .sisyphus/evidence/task-10-makefile.txt
  ```

  **Commit**: YES
  - Message: `test: add integration test runner and documentation`
  - Files: `tests/scripts/run_integration_tests.py`, `README.md`, `tests/README.md`, `Makefile`
  - Pre-commit: `make test-quick`

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Verify all deliverables exist, all "Must Have" implemented, all "Must NOT Have" avoided.

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check`, `mypy`, `pytest`. Review for code quality.

- [x] F3. **Integration Test Run** — `unspecified-high`
  Execute full integration test workflow, capture evidence.

- [x] F4. **Documentation Accuracy Check** — `unspecified-high`
  Verify README instructions work as documented.

---

## Commit Strategy

| Commit | Tasks | Message |
|--------|-------|---------|
| 1 | 1-3 | `test: add test_data directory structure and setup scripts` |
| 2 | 4-7 | `test: add noise injection framework and extended override tests` |
| 3 | 8-10 | `test: add integration test runner and documentation` |

---

## Success Criteria

### Verification Commands
```bash
# Setup test data
uv run python tests/scripts/setup_test_data.py

# Run unit tests (no Docker needed)
make test-quick

# Run integration tests (requires Docker)
make test-integration

# Run all tests
make test-all
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] Documentation accurate
- [ ] `chl/` directory never modified
