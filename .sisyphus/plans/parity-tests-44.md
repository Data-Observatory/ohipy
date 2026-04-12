# 44 R vs Python Parity Tests

## TL;DR

> **Quick Summary**: Create comprehensive parity testing framework with 44 tests comparing R and Python outputs across 4 datasets (original + 3 noise levels) and 11 variations per dataset (baseline, weights, pressure removal, resilience removal).
>
> **Deliverables**:
> - `tests/parity/setup_fixtures.py` - R fixture generation script
> - `tests/test_parity_full.py` - 44 parity tests
> - `comparative/cache/` - Noisy layer data
> - `comparative/fixtures/` - R output fixtures (44 CSVs)
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - R runs can be parallelized
> **Critical Path**: Setup fixtures → Run tests

---

## Context

### Original Request
User wants 44 R vs Python parity tests organized as:
- 4 datasets: original, noise 1%, noise 5%, noise 10%
- 11 variations per dataset: 1 baseline + 4 weights + 3 pressures + 3 resilience

### Current State
- Baseline parity test exists (`test_r_parity.py`)
- Noise/weight/matrix modifiers exist (`tests/parity/data_modifiers.py`)
- R runs via Docker (`ohicore-r-env` image)

### Key Decisions
1. R fixtures stored in `comparative/fixtures/` for compatibility
2. Noisy layer cache stored in `comparative/cache/`
3. Setup runs only if fixtures missing (unless `--overwrite` flag)
4. All noise levels use `seed=42` for reproducibility

---

## Work Objectives

### Core Objective
Create 44 parity tests that verify Python matches R across all data/config combinations.

### Concrete Deliverables
- `tests/parity/setup_fixtures.py` - Script to generate R fixtures
- `tests/test_parity_full.py` - 44 parametrized tests
- `comparative/cache/noise_*_seed42/` - 3 noisy layer directories
- `comparative/fixtures/{dataset}/{variation}.csv` - 44 R output files

### Definition of Done
- [ ] `uv run pytest tests/test_parity_full.py` runs all 44 tests
- [ ] `uv run python tests/parity/setup_fixtures.py` generates all fixtures
- [ ] `uv run python tests/parity/setup_fixtures.py --check` verifies fixtures exist
- [ ] All 44 tests pass when R fixtures are present
- [ ] Tests skip gracefully when R fixtures missing (with setup instruction)

### Must Have
- R fixtures generated once, reused for all test runs
- Deterministic noise (seed=42)
- Clear error messages when fixtures missing

### Must NOT Have (Guardrails)
- DO NOT run R on every test execution (too slow)
- DO NOT modify `chl/` directory
- DO NOT commit noisy layer cache (add to .gitignore)
- DO NOT commit R fixtures to git (too large, add to .gitignore)

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (TDD approach)
- **Framework**: pytest with parametrize
- **Agent-Executed QA**: Compare Python output vs R fixture CSV

### QA Policy
Each test:
1. Apply modification to data/config
2. Run Python calculation
3. Load corresponding R fixture
4. Compare scores within tolerance (0.05)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - sequential):
├── Task 1: Create fixture directory structure [quick]
├── Task 2: Update .gitignore for cache/fixtures [quick]
└── Task 3: Create setup_fixtures.py skeleton [quick]

Wave 2 (Setup script - can parallelize internal R runs):
├── Task 4: Implement noisy layer generation [quick]
├── Task 5: Implement R runner with custom paths [unspecified-high]
├── Task 6: Implement fixture generation loop [unspecified-high]
└── Task 7: Add --check and --overwrite CLI flags [quick]

Wave 3 (Test file):
├── Task 8: Create test_parity_full.py with parametrization [unspecified-high]
├── Task 9: Implement fixture existence check in tests [quick]
└── Task 10: Implement all 44 test cases [unspecified-high]

Wave 4 (Verification):
├── Task 11: Run setup_fixtures.py to generate R fixtures [unspecified-high]
├── Task 12: Run all 44 tests and verify pass [unspecified-high]
└── Task 13: Update tests/README.md [writing]

Critical Path: Task 1-3 → Task 4-7 → Task 8-10 → Task 11-13
```

---

## TODOs

- [ ] 1. Create fixture directory structure

  **What to do**:
  - Create `comparative/cache/` directory for noisy layers
  - Create `comparative/fixtures/` directory for R outputs
  - Structure: `fixtures/{dataset}/{variation}.csv`

  **Files**:
  - `comparative/cache/.gitkeep`
  - `comparative/fixtures/.gitkeep`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**: Can run immediately

  **Acceptance Criteria**:
  - [ ] `comparative/cache/` exists
  - [ ] `comparative/fixtures/` exists

---

- [ ] 2. Update .gitignore for cache/fixtures

  **What to do**:
  - Add `comparative/cache/` to .gitignore
  - Add `comparative/fixtures/` to .gitignore
  - These are generated files, should not be committed

  **Files**:
  - `.gitignore`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**: Can run with Task 1

  **Acceptance Criteria**:
  - [ ] `.gitignore` contains `comparative/cache/`
  - [ ] `.gitignore` contains `comparative/fixtures/`

---

- [ ] 3. Create setup_fixtures.py skeleton

  **What to do**:
  - Create `tests/parity/setup_fixtures.py` with CLI interface
  - Define constants: datasets, variations, paths
  - Add argparse with --check, --overwrite, --parallel flags

  **Files**:
  - `tests/parity/setup_fixtures.py`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**: After Tasks 1-2

  **Acceptance Criteria**:
  - [ ] `uv run python tests/parity/setup_fixtures.py --help` shows usage
  - [ ] Constants defined for all 44 combinations

---

- [ ] 4. Implement noisy layer generation

  **What to do**:
  - Use existing `inject_noise_to_layers()` from `data_modifiers.py`
  - Generate 3 noisy layer directories in `comparative/cache/`
  - Names: `noise_1pct_seed42`, `noise_5pct_seed42`, `noise_10pct_seed42`

  **Files**:
  - `tests/parity/setup_fixtures.py`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**: After Task 3

  **References**:
  - `tests/parity/data_modifiers.py:inject_noise_to_layers()` - Existing noise function

  **Acceptance Criteria**:
  - [ ] `comparative/cache/noise_1pct_seed42/layers/csv/` contains 227 CSV files
  - [ ] `comparative/cache/noise_5pct_seed42/layers/csv/` contains 227 CSV files
  - [ ] `comparative/cache/noise_10pct_seed42/layers/csv/` contains 227 CSV files

---

- [ ] 5. Implement R runner with custom paths

  **What to do**:
  - Create function to run R via Docker with custom:
    - Layers directory (for noise datasets)
    - Config directory (for weight/matrix modifications)
  - Output path for scores CSV
  - Use existing Docker pattern from `comparative/calculate_scores.r`

  **Files**:
  - `tests/parity/setup_fixtures.py`
  - `tests/parity/r_runner.py` (update existing)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**: After Task 3

  **References**:
  - `comparative/calculate_scores.r` - Existing R calculation script
  - `tests/parity/r_runner.py` - Existing R runner (may need updates)

  **Acceptance Criteria**:
  - [ ] Function `_run_r_calculation(layers_dir, conf_dir, output_csv)` works
  - [ ] Handles Docker errors gracefully

---

- [ ] 6. Implement fixture generation loop

  **What to do**:
  - Loop over 4 datasets × 11 variations = 44 combinations
  - For each:
    1. Apply modification (if needed)
    2. Run R with modified paths
    3. Save output to `comparative/fixtures/{dataset}/{variation}.csv`
  - Support --overwrite flag to regenerate

  **Datasets**:
  - `original` - uses `data/layers/csv/`
  - `noise_1pct` - uses `comparative/cache/noise_1pct_seed42/layers/csv/`
  - `noise_5pct` - uses `comparative/cache/noise_5pct_seed42/layers/csv/`
  - `noise_10pct` - uses `comparative/cache/noise_10pct_seed42/layers/csv/`

  **Variations** (11 per dataset):
  - `baseline` - no modification
  - `weight_fis_0.5` - FIS weight × 0.5
  - `weight_fis_2.5_mar_1.5` - FIS × 2.5, MAR × 1.5
  - `weight_fp_1.5` - FP × 1.5
  - `weight_ao_0.5_tr_1.5` - AO × 0.5, TR × 1.5
  - `pressure_po_fishing` - remove po_fishing
  - `pressure_po_water_pollution` - remove po_water_pollution
  - `pressure_both` - remove both pressures
  - `resilience_res_mpa` - remove res_mpa
  - `resilience_res_water` - remove res_water
  - `resilience_both` - remove both resiliences

  **Files**:
  - `tests/parity/setup_fixtures.py`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**: After Tasks 4-5

  **Acceptance Criteria**:
  - [ ] All 44 R fixtures generated
  - [ ] Each fixture has columns: region_id, goal, dimension, score

---

- [ ] 7. Add --check and --overwrite CLI flags

  **What to do**:
  - `--check`: Verify all 44 fixtures exist, exit 0 if OK, 1 if missing
  - `--overwrite`: Force regenerate all fixtures
  - `--parallel N`: Run N R processes in parallel (default: 1)

  **Files**:
  - `tests/parity/setup_fixtures.py`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**: After Task 6

  **Acceptance Criteria**:
  - [ ] `--check` returns 0 when all fixtures present
  - [ ] `--check` returns 1 and lists missing fixtures
  - [ ] `--overwrite` regenerates even if fixtures exist

---

- [ ] 8. Create test_parity_full.py with parametrization

  **What to do**:
  - Create new test file with pytest.mark.parametrize
  - Parametrize over 4 datasets × 11 variations
  - Define fixture path pattern

  **Files**:
  - `tests/test_parity_full.py`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**: After Tasks 1-7

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_parity_full.py --collect-only` shows 44 tests

---

- [ ] 9. Implement fixture existence check in tests

  **What to do**:
  - Add pytest fixture or skip condition
  - If R fixtures missing, skip with instruction to run setup
  - Use `--check` mode to verify

  **Files**:
  - `tests/test_parity_full.py`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**: After Task 8

  **Acceptance Criteria**:
  - [ ] Tests skip with clear message when fixtures missing
  - [ ] Message includes: `uv run python tests/parity/setup_fixtures.py`

---

- [ ] 10. Implement all 44 test cases

  **What to do**:
  - For each test:
    1. Apply same modification as R fixture
    2. Run Python calculation
    3. Load R fixture CSV
    4. Compare within tolerance (0.05)
  - Use existing `_compare_scores()` helper

  **Files**:
  - `tests/test_parity_full.py`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**: After Tasks 8-9

  **References**:
  - `tests/test_parity_scenarios.py:_compare_scores()` - Existing comparison helper
  - `tests/parity/data_modifiers.py` - Modification functions

  **Acceptance Criteria**:
  - [ ] All 44 tests compare Python vs R correctly
  - [ ] Failure shows which dataset/variation failed

---

- [ ] 11. Run setup_fixtures.py to generate R fixtures

  **What to do**:
  - Run: `uv run python tests/parity/setup_fixtures.py`
  - Verify all 44 fixtures generated
  - This is slow (~30-60 minutes), run once

  **Command**:
  ```bash
  uv run python tests/parity/setup_fixtures.py --parallel 4
  ```

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**: After Tasks 1-7

  **Acceptance Criteria**:
  - [ ] `comparative/fixtures/` contains 4 subdirectories
  - [ ] Each subdirectory contains 11 CSV files
  - [ ] Total: 44 R fixture files

---

- [ ] 12. Run all 44 tests and verify pass

  **What to do**:
  - Run: `uv run pytest tests/test_parity_full.py -v`
  - Verify all 44 tests pass
  - Fix any failures

  **Command**:
  ```bash
  uv run pytest tests/test_parity_full.py -v
  ```

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**: After Tasks 8-11

  **Acceptance Criteria**:
  - [ ] All 44 tests pass
  - [ ] No unexpected failures

---

- [ ] 13. Update tests/README.md

  **What to do**:
  - Document new parity test structure
  - Add setup instructions
  - Add commands to run tests

  **Files**:
  - `tests/README.md`

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: []

  **Parallelization**: After Task 12

  **Acceptance Criteria**:
  - [ ] README explains 44 parity tests
  - [ ] Setup command documented
  - [ ] Test commands documented

---

## Final Verification Wave

- [ ] F1. Run `uv run python tests/parity/setup_fixtures.py --check` → all 44 fixtures present
- [ ] F2. Run `uv run pytest tests/test_parity_full.py -v` → 44 tests pass
- [ ] F3. Verify `comparative/cache/` and `comparative/fixtures/` in .gitignore
- [ ] F4. Update tests/README.md with new test documentation

---

## Commit Strategy

- **Commit 1**: `feat(tests): add R fixture setup script and 44 parity tests`
  - Files: `tests/parity/setup_fixtures.py`, `tests/test_parity_full.py`, `.gitignore`
  - Pre-commit: `uv run pytest tests/test_parity_full.py --collect-only`

---

## Success Criteria

### Verification Commands
```bash
# Check fixtures exist
uv run python tests/parity/setup_fixtures.py --check

# Generate fixtures (one-time, slow)
uv run python tests/parity/setup_fixtures.py

# Force regenerate
uv run python tests/parity/setup_fixtures.py --overwrite

# Run all 44 tests
uv run pytest tests/test_parity_full.py -v

# Expected: 44 passed
```

### Final Checklist
- [ ] All 44 R fixtures generated in `comparative/fixtures/`
- [ ] All 44 tests pass
- [ ] Cache and fixtures in .gitignore
- [ ] Documentation updated
