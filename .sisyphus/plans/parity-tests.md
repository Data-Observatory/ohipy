# Comprehensive R-vs-Python Parity Test Overhaul

## TL;DR

> **Quick Summary**: Fix the comparison infrastructure (outer join + symmetric NaN), tighten tolerance from 0.05 to 0.01, add a layer audit gate for all 98 declared layers, and add edge-case tests. All 44 existing parity tests are migrated to the new comparison helper.
> 
> **Deliverables**:
> - New shared comparison helper module (`tests/helpers/comparison.py`)
> - Layer audit gate test (`tests/test_layer_audit.py`)
> - Updated parity tests using improved comparison (0.01 tolerance)
> - Updated `compare_scores.py` standalone script
> - pytest markers for tiered test execution
> - Hard-fail on missing layers during parity tests
> 
> **Estimated Effort**: Medium (1-2 days)
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 (comparison helper) → Task 4-6 (parity migration) → Task 8-9 (edge cases)

---

## Context

### Original Request
Create comprehensive R-vs-Python parity tests covering ALL layers, ALL goals, ALL dimensions with 0.01 tolerance. Fix incomplete fixture coverage. Validate layers have data (some regions can be missing, but not completely empty).

### Interview Summary
**Key Discussions**:
- Input surface traced: `calculate_all(config, layers)` with lazy-loading. `OHIRunner` supports overrides (weights, disable pressures/resiliences, matrices).
- Year discrimination gap identified: `load_layers()` always loads 2024 files regardless of `scenario_year`. Scaffolding exists but upstream is hardcoded. **Out of scope for this plan** — test what exists.
- Fixture coverage: 39/98 layers, zero coverage for 11 goals. Silent failures (print warning, no raise).
- Current parity: 44 tests (4 datasets × 11 variations), tolerance 0.05, inner join, no symmetric NaN check.
- `data/` folder: needed by scripts and parity tests, cannot be deleted or moved.

**Research Findings**:
- Oracle confirmed tiered approach, outer join, symmetric NaN, dimension-first reporting
- 18 goals, 6 dimensions, ~9,477 score rows per dataset
- Noise: bootstrap resampling (NOT Gaussian), seed=42, precomputed cached files
- Layer→goal mapping: ~34 goal-specific + 30 pressure + 26 resilience = ~92 unique minimum layers

### Metis Review
**Identified Gaps** (addressed):
- Tolerance semantics: absolute 0.01 in 0-100 score space (scores are 0-100 in CSV output)
- "ALL layers" = 98 declared in `data/layers.csv`, not all 227 files on disk
- "layers have data" = file exists + non-empty DataFrame + not all-null in value columns (some regions can be missing)
- Comparison helper must assert key uniqueness before joining
- Must not change calculation logic to "make tests pass"
- Noise datasets are deterministic (precomputed fixtures, seed=42)
- NaN representation: treat R NA and Python NaN as equivalent (both sides NaN → pass; one side NaN → fail)
- Layer audit mapping derived from `layers.csv` metadata
- `scenario_year` / year loading fix is out of scope — test what exists

---

## Work Objectives

### Core Objective
Fix false-pass risks in parity comparison (inner join, one-sided NaN, loose tolerance), add data integrity gate (all 98 layers present + non-empty), and ensure tiered test execution with pytest markers.

### Concrete Deliverables
- `tests/helpers/comparison.py` — shared comparison module
- `tests/test_layer_audit.py` — 98-layer integrity gate
- Updated `tests/test_r_parity.py` — uses new comparison, 0.01 tolerance
- Updated `tests/test_parity_full.py` — uses new comparison, 0.01 tolerance
- Updated `tests/comparative/compare_scores.py` — outer join, 0.01 tolerance
- Updated `tests/conftest.py` — pytest markers + hard-fail fixture
- Updated `tests/run_all_tests.sh` — tier support

### Definition of Done
- [ ] `uv run pytest -m integrity` passes: all 98 layers validated
- [ ] `uv run pytest -m parity` passes: baseline parity at 0.01 tolerance
- [ ] `uv run pytest -m parity_full` passes: all 44 variations at 0.01 tolerance
- [ ] Outer join comparison detects missing rows (no false passes)
- [ ] Symmetric NaN check catches one-sided NaN (no false passes)
- [ ] Key uniqueness asserted before comparison

### Must Have
- Outer join (not inner) on `(region_id, goal, dimension)` for all comparisons
- Symmetric NaN rule: both NaN → pass; exactly one NaN → fail
- Key uniqueness assertion on both sides before joining
- Tolerance = 0.01 absolute in 0-100 score space
- All 98 declared layers checked for: exists, loadable, non-empty, not-all-null value columns
- Dimension-first failure reporting (group by dimension, then goal)
- pytest markers: `integrity`, `parity`, `parity_full`
- Hard-fail on missing layers during parity tests (not just print warning)

### Must NOT Have (Guardrails)
- **NO** changes to calculation logic, rounding, or calculation order
- **NO** changes to `src/ohipy/` source code (except maybe `load_layers` hard-fail option)
- **NO** fixing of year/scenario loading (known limitation, out of scope)
- **NO** modification of `tests/comparative/scores_2024_r.csv` (immutable R reference)
- **NO** new synthetic data generation — use existing real data + noise caches
- **NO** generalized data validation framework — only what parity needs
- **NO** AI slop: no excessive comments, no over-abstraction, no generic names

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (this IS a test plan — tests are the deliverable)
- **Framework**: pytest with polars assertions
- **TDD**: Not applicable — we're writing tests themselves

### QA Policy
Every task includes agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Comparison helper**: Use Bash (python -c) — import, call functions, assert outputs
- **Layer audit**: Use Bash (pytest) — run test, verify pass/fail
- **Parity tests**: Use Bash (pytest) — run with markers, check exit codes

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - foundation):
├── Task 1: Create shared comparison helper module [quick]
├── Task 2: Add pytest markers + hard-fail fixture [quick]
└── Task 3: Create layer audit gate test [quick]

Wave 2 (After Wave 1 - core migration):
├── Task 4: Migrate test_r_parity.py to new comparison (depends: 1, 2) [quick]
├── Task 5: Migrate test_parity_full.py to new comparison (depends: 1, 2) [unspecified-high]
├── Task 6: Update compare_scores.py standalone script (depends: 1) [quick]
└── Task 7: Add dimension-level failure reporting tests (depends: 1) [unspecified-high]

Wave 3 (After Wave 2 - coverage + validation):
├── Task 8: Add edge case / type safety tests (depends: 1, 4, 5) [unspecified-high]
├── Task 9: Update test runner script with tier support (depends: 2, 3, 4, 5) [quick]
└── Task 10: Document test architecture in tests/AGENTS.md (depends: all) [writing]

Wave FINAL (After ALL tasks — 4 parallel reviews, then user okay):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: Task 1 → Task 5 → Task 8 → F1-F4 → user okay
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 3 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | - | 4, 5, 6, 7, 8 | 1 |
| 2 | - | 4, 5, 9 | 1 |
| 3 | - | 9 | 1 |
| 4 | 1, 2 | 8, 9 | 2 |
| 5 | 1, 2 | 8, 9 | 2 |
| 6 | 1 | 9 | 2 |
| 7 | 1 | 8 | 2 |
| 8 | 1, 4, 5 | 9, 10 | 3 |
| 9 | 2, 3, 4, 5 | 10 | 3 |
| 10 | all | F1-F4 | 3 |

### Agent Dispatch Summary

- **Wave 1**: 3 — T1 → `quick`, T2 → `quick`, T3 → `quick`
- **Wave 2**: 4 — T4 → `quick`, T5 → `unspecified-high`, T6 → `quick`, T7 → `unspecified-high`
- **Wave 3**: 3 — T8 → `unspecified-high`, T9 → `quick`, T10 → `writing`
- **FINAL**: 4 — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. Create Shared Comparison Helper Module

  **What to do**:
  - Create `tests/helpers/__init__.py` (empty) and `tests/helpers/comparison.py`
  - Implement `compare_scores(py_df, r_df, tolerance=0.01, join_cols=None)` function that:
    1. Defaults `join_cols` to `["region_id", "goal", "dimension"]`
    2. Asserts key uniqueness on both sides (fail with duplicate examples if violated)
    3. Performs **outer join** (not inner) on join_cols
    4. Detects rows missing from Python side (`_merge == "left_only"` equivalent in polars)
    5. Detects rows missing from R side (`_merge == "right_only"` equivalent)
    6. Applies **symmetric NaN rule**: both NaN → pass; exactly one NaN → fail
    7. For non-NaN pairs: checks `abs(score_py - score_r) > tolerance`
    8. Rounds scores to 2 decimal places before comparing (matching current behavior)
    9. Returns a structured result: `ComparisonResult` NamedTuple with fields: `max_diff`, `failure_count`, `py_missing_count`, `r_missing_count`, `nan_mismatch_count`, `failures_df`, `summary_df`
  - Implement `format_failure_report(result, dataset=None, variation=None) -> str` that:
    1. Groups failures by `dimension` first, then `goal` (dimension-first reporting)
    2. Reports: total failures, missing-from-Py count, missing-from-R count, NaN mismatch count
    3. Lists top-10 worst offending (dimension, goal) pairs with max_diff and count
    4. Includes full diff path for investigation
  - Implement `assert_parity(result, dataset=None, variation=None)` that calls `format_failure_report` and raises `AssertionError` with the formatted message

  **Must NOT do**:
  - Do NOT use pandas — use polars only (project convention)
  - Do NOT change any rounding behavior in the comparison
  - Do NOT modify `src/ohipy/` code
  - Do NOT use inner join

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single file creation with clear spec, pure utility function
  - **Skills**: []
    - No special skills needed — standard Python/polars code

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 2, 3)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 4, 5, 6, 7, 8
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - `tests/test_parity_full.py:163-191` — Current `_compare_scores()` function. Use as starting point but fix: inner→outer join, add symmetric NaN, add missing-row detection, add key uniqueness assertion
  - `tests/test_r_parity.py:119-164` — Current NaN check pattern (`is_nan()` filter). Shows existing NaN handling approach but one-sided only

  **API/Type References**:
  - Polars `join()` with `how="full"` and `coalesce()` for outer join — see polars docs for full join with indicator
  - `polars.DataFrame.filter()`, `is_nan()`, `null()` — for NaN/null handling

  **External References**:
  - Polars join docs: https://docs.pola.rs/api/python/dataframe/api/polars.DataFrame.join.html — full join semantics and suffix handling

  **WHY Each Reference Matters**:
  - `_compare_scores()` is the code being replaced — must preserve its good parts (group_by aggregation, diff reporting) while fixing the join/NaN issues
  - `test_r_parity.py` shows the existing NaN detection pattern that needs to be made symmetric

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Outer join detects missing rows from R side
    Tool: Bash (python -c)
    Preconditions: Python output has all rows, R output missing some rows
    Steps:
      1. Create py_df with 5 rows: region_id=[0,1,2,3,4], goal="FIS", dimension="score", score=[80,75,70,65,60]
      2. Create r_df with 3 rows: region_id=[0,1,2], goal="FIS", dimension="score", score=[80,75,70]
      3. result = compare_scores(py_df, r_df, tolerance=0.01)
      4. Assert result.r_missing_count == 2
      5. Assert result.failure_count >= 2
    Expected Result: r_missing_count=2, failure detected for missing rows
    Failure Indicators: r_missing_count == 0 (inner join false pass)
    Evidence: .sisyphus/evidence/task-1-outer-join.txt

  Scenario: Symmetric NaN - one-sided NaN detected
    Tool: Bash (python -c)
    Preconditions: Python has NaN where R has value
    Steps:
      1. Create py_df with score=[float("nan"), 75.0]
      2. Create r_df with score=[80.0, 75.0]
      3. result = compare_scores(py_df, r_df, tolerance=0.01)
      4. Assert result.nan_mismatch_count == 1
      5. Assert result.failure_count >= 1
    Expected Result: nan_mismatch_count=1, failure detected
    Failure Indicators: nan_mismatch_count == 0 (NaN ignored silently)
    Evidence: .sisyphus/evidence/task-1-symmetric-nan.txt

  Scenario: Both-sides NaN passes (not a failure)
    Tool: Bash (python -c)
    Steps:
      1. Create py_df and r_df both with score=[float("nan"), 75.0]
      2. result = compare_scores(py_df, r_df, tolerance=0.01)
      3. Assert result.nan_mismatch_count == 0
      4. Assert result.failure_count == 0
    Expected Result: Both-NaN treated as equal, no failure
    Failure Indicators: nan_mismatch_count > 0 (over-sensitive)
    Evidence: .sisyphus/evidence/task-1-both-nan.txt

  Scenario: Key uniqueness assertion catches duplicates
    Tool: Bash (python -c)
    Steps:
      1. Create py_df with duplicate keys: 2 rows with (region_id=1, goal="FIS", dimension="score")
      2. Assert that compare_scores raises AssertionError with "duplicate" in message
    Expected Result: AssertionError raised mentioning duplicate keys
    Failure Indicators: No error raised (joins silently produce wrong results)
    Evidence: .sisyphus/evidence/task-1-key-uniqueness.txt

  Scenario: Tolerance 0.01 catches diff of 0.02
    Tool: Bash (python -c)
    Steps:
      1. py_df score=75.01, r_df score=75.03 (diff=0.02)
      2. result = compare_scores(py_df, r_df, tolerance=0.01)
      3. Assert result.failure_count == 1
    Expected Result: Failure detected for 0.02 > 0.01
    Failure Indicators: failure_count == 0 (tolerance too loose)
    Evidence: .sisyphus/evidence/task-1-tolerance.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `test(parity): add shared comparison helper with outer join and symmetric NaN`
  - Files: `tests/helpers/__init__.py`, `tests/helpers/comparison.py`
  - Pre-commit: `uv run python -c "from tests.helpers.comparison import compare_scores, assert_parity; print('OK')"`

- [x] 2. Add pytest Markers + Hard-Fail Fixture

  **What to do**:
  - Register pytest markers in `pyproject.toml` `[tool.pytest.ini_options]` section (or `pytest.ini`):
    - `integrity` — fast, no-Docker data integrity tests
    - `parity` — baseline R parity (Docker needed for fixture generation)
    - `parity_full` — comprehensive 44-variation parity (Docker + fixtures)
  - Update `tests/conftest.py`:
    - Add a `load_layers_strict` fixture or helper that calls `load_layers()` and then **asserts** all layers declared in `layers.csv` are present in the result (no silent `print()` warnings). If any declared layer with non-null filename is missing from `layers_data`, raise with the list of missing layer names.
    - Add a `pytest_configure` hook to register the markers
  - The hard-fail check: for each row in `layers.csv` where `filename` is not null, assert `layer_name in layers_data` and `len(layers_data[layer_name]) > 0`

  **Must NOT do**:
  - Do NOT modify `src/ohipy/layers/__init__.py` — keep the warning-based behavior there
  - Do NOT change existing fixture signatures (backward compatible)
  - Do NOT add markers to tests that don't exist yet

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small config change + small conftest addition
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 1, 3)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 4, 5, 9
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `tests/conftest.py` — Current fixtures (5 total). Add new fixtures alongside existing ones, don't replace
  - `pyproject.toml` — Current project config. Add `[tool.pytest.ini_options].markers` list

  **API/Type References**:
  - `pytest.ini_options` markers syntax: `markers = ["integrity: ...", "parity: ...", "parity_full: ..."]`
  - `src/ohipy/layers/__init__.py:38-78` — The load_layers loop that currently prints warnings. The hard-fail fixture replicates this check with assertions

  **WHY Each Reference Matters**:
  - conftest.py is being extended, not rewritten
  - layers/__init__.py shows which rows get skipped (filename is None) and which produce warnings

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: pytest markers are registered and discoverable
    Tool: Bash
    Steps:
      1. Run: uv run pytest --markers
      2. Assert output contains "integrity", "parity", "parity_full"
    Expected Result: All 3 markers listed with descriptions
    Failure Indicators: "unknown marker" error when running tests
    Evidence: .sisyphus/evidence/task-2-markers.txt

  Scenario: Hard-fail fixture detects missing layer
    Tool: Bash (python -c)
    Steps:
      1. Create a minimal config pointing to a directory with a layers.csv listing "nonexistent_layer" with filename "missing.csv"
      2. Call load_layers() → get layers dict (warning printed, layer missing)
      3. Run the strict check logic: assert all declared layers present
      4. Expect AssertionError listing "nonexistent_layer"
    Expected Result: AssertionError with missing layer name
    Failure Indicators: No error (silent pass)
    Evidence: .sisyphus/evidence/task-2-hard-fail.txt

  Scenario: Existing tests still pass with new conftest
    Tool: Bash
    Steps:
      1. Run: uv run pytest tests/test_overrides.py tests/test_runner_basic.py -v
      2. Assert exit code 0, all tests pass
    Expected Result: All existing tests pass unchanged
    Failure Indicators: Any test failure or error
    Evidence: .sisyphus/evidence/task-2-existing-tests.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `test(parity): add pytest markers and hard-fail layer loading fixture`
  - Files: `tests/conftest.py`, `pyproject.toml`
  - Pre-commit: `uv run pytest tests/test_overrides.py tests/test_runner_basic.py -v`

- [x] 3. Create Layer Audit Gate Test

  **What to do**:
  - Create `tests/test_layer_audit.py`
  - Mark with `@pytest.mark.integrity`
  - Test 1 — `test_all_declared_layers_exist`: Load `data/layers.csv`, for each row where `filename` is not null, verify the corresponding file exists in `data/layers/parquet/` (preferred) or `data/layers/csv/` (fallback). Report all missing files at once (not one-at-a-time).
  - Test 2 — `test_all_declared_layers_loadable`: Load config + layers via `load_config()` + `load_layers()`, verify all declared layers (non-null filename) are present in `layers["data"]`. Report all missing at once.
  - Test 3 — `test_all_loaded_layers_nonempty`: For each loaded layer, assert `len(df) > 0` (non-empty DataFrame). Report all empty at once.
  - Test 4 — `test_all_loaded_layers_have_data`: For each loaded layer, check that not ALL value columns (non-ID columns like rgn_id, year, region_id) are entirely null. At least one row must have a non-null value in a data column. Report all fully-null layers at once.
  - Test 5 — `test_no_duplicate_layer_keys`: Verify no duplicate `layer` names in `layers.csv`.
  - On failure, report comprehensive list: "Missing: [X, Y, Z]. Empty: [A, B]. All-null: [C, D]."

  **Must NOT do**:
  - Do NOT use `tests/fixtures/` data — this tests `data/` (the real reference dataset)
  - Do NOT modify any data files
  - Do NOT check files on disk that aren't in `layers.csv` (year variants are out of scope)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single test file with 5 straightforward test functions
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 1, 2)
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 9
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `tests/test_parity_full.py:40-45` — How to define DATA_DIR, CONF_DIR, LAYERS_DIR constants pointing to `data/`
  - `tests/conftest.py:12-16` — How to load default config via `load_config()`

  **API/Type References**:
  - `data/layers.csv` — 98 data rows (99 lines with header), columns: `layer`, `filename`, `targets`, `fld_value`, `fld_id`, `fld_year` (check exact columns)
  - `src/ohipy/layers/__init__.py:38-44` — Row iteration pattern: skip when `filename is None`

  **WHY Each Reference Matters**:
  - test_parity_full.py shows the established pattern for referencing data/ directory
  - layers.csv is the authoritative source of which layers should exist
  - layers/__init__.py shows which rows are skipped (filename=None) so audit skips them too

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Layer audit passes for all 98 declared layers
    Tool: Bash
    Steps:
      1. Run: uv run pytest tests/test_layer_audit.py -v
      2. Assert all 5 tests pass
      3. Count lines in output matching "PASSED" — expect 5
    Expected Result: 5 tests pass, 0 failures
    Failure Indicators: Any test failure listing missing/empty/all-null layers
    Evidence: .sisyphus/evidence/task-3-audit-pass.txt

  Scenario: Layer audit catches a simulated missing file
    Tool: Bash (python -c)
    Steps:
      1. Load layers.csv, pick first row's filename
      2. Temporarily check that if filename were "FAKE_MISSING.csv", the existence check would fail
      3. Verify error message includes "FAKE_MISSING"
    Expected Result: Existence check returns False for fake filename
    Failure Indicators: Existence check returns True (path logic wrong)
    Evidence: .sisyphus/evidence/task-3-missing-detect.txt

  Scenario: Layer audit runs in integrity tier only
    Tool: Bash
    Steps:
      1. Run: uv run pytest -m integrity -v
      2. Assert test_layer_audit tests are collected and run
      3. Run: uv run pytest -m parity -v --collect-only
      4. Assert test_layer_audit tests are NOT collected
    Expected Result: Audit tests in integrity tier, not in parity tier
    Failure Indicators: Audit tests appear in wrong tier
    Evidence: .sisyphus/evidence/task-3-tier.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `test(parity): add layer audit gate for all 98 declared layers`
  - Files: `tests/test_layer_audit.py`
  - Pre-commit: `uv run pytest tests/test_layer_audit.py -v`

- [x] 4. Migrate test_r_parity.py to New Comparison

  **What to do**:
  - Update `tests/test_r_parity.py` to:
    1. Import `compare_scores`, `assert_parity` from `tests.helpers.comparison`
    2. Change `TOLERANCE` from `0.05` to `0.01`
    3. Replace the inline comparison logic in `test_python_matches_r()` with a call to `compare_scores()` + `assert_parity()`
    4. Remove the inline `_compare_scores` equivalent code (the join + NaN check + group_by logic)
    5. Keep `_generate_r_fixture()` and `_generate_py_scores()` as-is (they work fine)
    6. Keep the AUTO_GEN environment variable logic
  - Mark test with `@pytest.mark.parity`

  **Must NOT do**:
  - Do NOT change R fixture generation logic
  - Do NOT change Python score generation logic
  - Do NOT modify the tolerance to anything other than 0.01

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single file, replacing inline code with helper call
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 5, 6, 7)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 8, 9
  - **Blocked By**: Tasks 1, 2

  **References**:

  **Pattern References**:
  - `tests/test_r_parity.py` — Current file being modified (168 lines). The comparison logic at lines 119-164 is what gets replaced
  - `tests/helpers/comparison.py` (Task 1) — The new module to import from

  **WHY Each Reference Matters**:
  - The current file IS the modification target — everything stays except lines 119-164 (comparison) and line 22 (TOLERANCE)

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Migrated test detects missing rows (outer join)
    Tool: Bash
    Steps:
      1. Verify test_r_parity.py imports from tests.helpers.comparison
      2. Run: grep -c "compare_scores" tests/test_r_parity.py — expect at least 1
      3. Run: grep "TOLERANCE = 0.01" tests/test_r_parity.py — expect match
    Expected Result: Uses comparison helper, tolerance is 0.01
    Failure Indicators: TOLERANCE still 0.05, no import from helpers
    Evidence: .sisyphus/evidence/task-4-migration.txt

  Scenario: Migrated test still passes with valid data
    Tool: Bash
    Preconditions: R fixture and Python output exist
    Steps:
      1. Run: uv run pytest tests/test_r_parity.py -v -k test_python_matches_r
      2. If R fixture missing: skip (expected in CI without Docker)
      3. If fixture present: assert test passes or fails with 0.01 tolerance details
    Expected Result: Test runs with new comparison, provides dimension-first reporting
    Failure Indicators: Import error, AttributeError
    Evidence: .sisyphus/evidence/task-4-r-parity.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `test(parity): migrate baseline parity to 0.01 tolerance with outer-join comparison`
  - Files: `tests/test_r_parity.py`
  - Pre-commit: `uv run python -c "from tests.test_r_parity import *; print('import OK')"`

- [x] 5. Migrate test_parity_full.py to New Comparison

  **What to do**:
  - Update `tests/test_parity_full.py` to:
    1. Import `compare_scores`, `assert_parity` from `tests.helpers.comparison`
    2. Change `TOLERANCE` from `0.05` to `0.01`
    3. Replace the inline `_compare_scores()` function (lines 163-191) with the imported `compare_scores()`
    4. Update `test_parity_full()` to use `assert_parity()` instead of the current `assert result["failure_count"] == 0`
    5. Delete the local `_compare_scores()` function entirely
    6. Mark test with `@pytest.mark.parity_full` (in addition to existing parametrize marks)
  - Verify all 44 parametrized test IDs still work correctly with the new comparison

  **Must NOT do**:
  - Do NOT change the parametrize configuration (datasets, variations)
  - Do NOT change the fixture bootstrap logic
  - Do NOT change the weight/pressure/resilience override configurations
  - Do NOT change `_run_py_calculation()` or `_get_layers_dir()`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 304-line file with 44 parametrized tests, needs careful migration
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 6, 7)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 8, 9
  - **Blocked By**: Tasks 1, 2

  **References**:

  **Pattern References**:
  - `tests/test_parity_full.py` — Current file being modified (304 lines)
  - `tests/helpers/comparison.py` (Task 1) — New comparison module

  **API/Type References**:
  - `tests/test_parity_full.py:163-191` — `_compare_scores()` function being replaced. It returns `{"max_diff", "failures", "failure_count", "py_count", "r_count"}`. The new `ComparisonResult` NamedTuple has equivalent fields.

  **WHY Each Reference Matters**:
  - The return value of `_compare_scores()` is used at line 300. Need to update assertion to use new result type
  - The parametrize at line 252-253 must stay intact

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Old _compare_scores function is removed
    Tool: Bash (grep)
    Steps:
      1. Run: grep -n "def _compare_scores" tests/test_parity_full.py
      2. Assert: no match (function removed)
      3. Run: grep -n "from tests.helpers.comparison import" tests/test_parity_full.py
      4. Assert: match found
    Expected Result: Local function removed, helper imported
    Failure Indicators: Old function still present, no import
    Evidence: .sisyphus/evidence/task-5-refactor.txt

  Scenario: Parametrized tests still collect as 44
    Tool: Bash
    Steps:
      1. Run: uv run pytest tests/test_parity_full.py --collect-only -q
      2. Count lines with "test_parity_full" — expect 44
    Expected Result: 44 tests collected (4 datasets × 11 variations)
    Failure Indicators: Wrong count (parametrize broken)
    Evidence: .sisyphus/evidence/task-5-parametrize.txt

  Scenario: Tolerance is 0.01 in test_parity_full.py
    Tool: Bash (grep)
    Steps:
      1. Run: grep "TOLERANCE = 0.01" tests/test_parity_full.py
      2. Assert match
    Expected Result: TOLERANCE = 0.01
    Failure Indicators: Still 0.05
    Evidence: .sisyphus/evidence/task-5-tolerance.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `test(parity): migrate 44-variation parity to 0.01 tolerance with shared comparison`
  - Files: `tests/test_parity_full.py`
  - Pre-commit: `uv run pytest tests/test_parity_full.py --collect-only -q`

- [x] 6. Update compare_scores.py Standalone Script

  **What to do**:
  - Update `tests/comparative/compare_scores.py` to:
    1. Import and use `compare_scores` from `tests.helpers.comparison`
    2. Change `tolerance` from `0.05` to `0.01`
    3. Replace the pandas-based comparison (lines 30-67) with the polars-based comparison helper
    4. Use outer join semantics (via the helper)
    5. Keep the "R local vs R remote" check (lines 34-43) but update to polars
    6. Print dimension-first failure report on failure
    7. Write detailed CSV with failures (same output file: `scores_difference.csv`)
  - This script is the standalone entry point (`python tests/comparative/compare_scores.py`)

  **Must NOT do**:
  - Do NOT remove the R-local-vs-R-remote verification step
  - Do NOT change the output file paths
  - Do NOT switch from pandas to polars for the R-remote URL fetch (keep pandas for that if needed, or convert to polars + `pl.read_csv`)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 71-line script, straightforward migration
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 5, 7)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 9
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `tests/comparative/compare_scores.py` — Current file being modified (71 lines)
  - `tests/helpers/comparison.py` (Task 1) — Module to import

  **WHY Each Reference Matters**:
  - The script does 2 checks: R-local==R-remote, then Py==R-local. Both need updating
  - Line 18: `tolerance = 0.05` → `0.01`
  - Lines 30-32: `merge()` with `how="left"` needs to become outer join via helper

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: compare_scores.py uses new comparison helper
    Tool: Bash
    Steps:
      1. Run: grep "from tests.helpers.comparison import" tests/comparative/compare_scores.py
      2. Assert: match found
      3. Run: grep "tolerance = 0.01" tests/comparative/compare_scores.py
      4. Assert: match found
    Expected Result: Helper imported, tolerance 0.01
    Failure Indicators: Still using inline comparison or 0.05
    Evidence: .sisyphus/evidence/task-6-standalone.txt

  Scenario: Script runs without import error
    Tool: Bash
    Steps:
      1. Run: uv run python -c "import tests.comparative.compare_scores; print('OK')"
      2. Assert: exit code 0
    Expected Result: Module imports cleanly
    Failure Indicators: ImportError or ModuleNotFoundError
    Evidence: .sisyphus/evidence/task-6-import.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `test(parity): update compare_scores.py to 0.01 tolerance with shared comparison`
  - Files: `tests/comparative/compare_scores.py`
  - Pre-commit: `uv run python -c "import tests.comparative.compare_scores; print('OK')"`

- [x] 7. Add Dimension-Level Failure Reporting Tests

  **What to do**:
  - Create `tests/test_comparison_helper.py` — unit tests for the comparison helper itself
  - Test that the comparison helper's dimension-first grouping works correctly:
    1. `test_format_failure_report_groups_by_dimension`: Create mock ComparisonResult with failures across multiple dimensions and goals. Verify `format_failure_report()` groups by dimension first (status, trend, pressures, resilience, future, score), then by goal within each dimension.
    2. `test_outer_join_detects_py_missing_rows`: R has rows that Py doesn't → py_missing_count > 0
    3. `test_outer_join_detects_r_missing_rows`: Py has rows that R doesn't → r_missing_count > 0
    4. `test_both_nan_passes`: Both sides NaN → not in failures
    5. `test_one_sided_nan_fails`: One side NaN, other has value → nan_mismatch_count > 0
    6. `test_duplicate_keys_raise`: Duplicate keys in either side → assertion error
    7. `test_tolerance_boundary`: Diff exactly at tolerance (0.01) → not a failure. Diff 0.01001 → failure
    8. `test_rounding_before_compare`: Scores rounded to 2dp before comparison
  - Mark all with `@pytest.mark.integrity`

  **Must NOT do**:
  - Do NOT use real R/Python score data — use synthetic DataFrames
  - Do NOT test anything beyond the comparison helper's behavior

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 8 targeted unit tests with careful edge-case design
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 5, 6)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 8
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `tests/test_overrides.py` — Example of focused unit tests in this project
  - `tests/helpers/comparison.py` (Task 1) — The module under test

  **WHY Each Reference Matters**:
  - test_overrides.py shows the testing style: direct function calls, assert on return values

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: All comparison helper unit tests pass
    Tool: Bash
    Steps:
      1. Run: uv run pytest tests/test_comparison_helper.py -v
      2. Assert all 8 tests pass
    Expected Result: 8 passed, 0 failed
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-7-helper-tests.txt

  Scenario: Tests run in integrity tier
    Tool: Bash
    Steps:
      1. Run: uv run pytest -m integrity tests/test_comparison_helper.py --collect-only -q
      2. Assert 8 tests collected
    Expected Result: All 8 tests in integrity tier
    Failure Indicators: 0 collected (missing markers)
    Evidence: .sisyphus/evidence/task-7-tier.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `test(parity): add unit tests for comparison helper edge cases`
  - Files: `tests/test_comparison_helper.py`
  - Pre-commit: `uv run pytest tests/test_comparison_helper.py -v`

- [x] 8. Add Edge Case and Type Safety Tests

  **What to do**:
  - Create `tests/test_edge_cases.py`
  - Test 1 — `test_region_id_type_consistency`: Load Python scores and R fixture. Verify both have `region_id` as integer type (not string). If types differ, comparison would silently produce wrong results.
  - Test 2 — `test_goal_case_consistency`: Verify goal codes match exactly (FIS vs fis would cause join misses). Check all 18 goals present in both outputs.
  - Test 3 — `test_dimension_names_consistency`: Verify dimension names match exactly between R and Python (status, trend, pressures, resilience, future, score). Check for trailing spaces, case differences.
  - Test 4 — `test_no_inf_values`: Verify neither R nor Python output contains Inf or -Inf values (these would bypass NaN checks).
  - Test 5 — `test_row_count_matches`: Verify both outputs have the same number of rows (outer join should find 0 missing on each side for baseline).
  - Test 6 — `test_global_region_present`: Verify region_id=0 (global/area-weighted) exists in both outputs for Index dimension.
  - Test 7 — `test_score_range`: All non-NaN scores should be in [0, 100] range (external scale). Flag any outside this range.
  - Mark all with `@pytest.mark.integrity`
  - All tests should work with pre-existing fixtures (skip if fixtures missing)

  **Must NOT do**:
  - Do NOT generate new R fixtures — use existing ones
  - Do NOT modify calculation code to fix any issues found
  - Do NOT add tests that require Docker

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple edge-case tests needing careful schema inspection
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 9, 10)
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 9, 10
  - **Blocked By**: Tasks 1, 4, 5

  **References**:

  **Pattern References**:
  - `tests/test_r_parity.py:119-120` — How R/Py DataFrames are loaded (schema: goal, dimension, region_id, score)
  - `tests/test_parity_full.py:163-191` — Score schema reference

  **API/Type References**:
  - `tests/comparative/scores_2024_r.csv` — Immutable R reference. Schema: goal(str), dimension(str), region_id(int), score(float)
  - 18 goal codes: FIS, MAR, FP, AO, NP, CS, CP, TR, LIV, ECO, LE, ICO, LSP, SP, CW, HAB, SPP, BD
  - 6 dimensions: status, trend, pressures, resilience, future, score

  **WHY Each Reference Matters**:
  - The R fixture CSV is the authoritative schema — region_id must be int, not string
  - Goal/dimension string matching must be exact for outer join to work correctly

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: All edge case tests pass
    Tool: Bash
    Steps:
      1. Run: uv run pytest tests/test_edge_cases.py -v
      2. Assert all tests pass (or skip if fixtures missing)
    Expected Result: 7 passed or skipped (no failures)
    Failure Indicators: Any test failure indicating schema/type mismatch
    Evidence: .sisyphus/evidence/task-8-edge-cases.txt

  Scenario: Edge case tests are in integrity tier
    Tool: Bash
    Steps:
      1. Run: uv run pytest -m integrity tests/test_edge_cases.py --collect-only -q
      2. Assert 7 tests collected
    Expected Result: 7 tests collected under integrity marker
    Failure Indicators: 0 collected
    Evidence: .sisyphus/evidence/task-8-tier.txt
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `test(parity): add edge case tests for schema, type, and range consistency`
  - Files: `tests/test_edge_cases.py`
  - Pre-commit: `uv run pytest tests/test_edge_cases.py -v`

- [x] 9. Update Test Runner Script with Tier Support

  **What to do**:
  - Update `tests/run_all_tests.sh` to support tiered execution:
    1. `--tier integrity` → runs only `uv run pytest -m integrity -v` (fast, no Docker)
    2. `--tier parity` → runs `uv run pytest -m parity -v` (baseline, needs R fixture)
    3. `--tier parity_full` → runs `uv run pytest -m parity_full -v` (full 44, needs Docker + fixtures)
    4. Default (no flag) → runs integrity + parity (skip parity_full by default)
    5. `--all` → runs all tiers
    6. Keep `--skip-docker` and `--no-fixtures` flags working
  - Add timing output per tier

  **Must NOT do**:
  - Do NOT break existing script behavior
  - Do NOT remove existing flags

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Shell script update with flag parsing
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 8, 10)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 2, 3, 4, 5

  **References**:

  **Pattern References**:
  - `tests/run_all_tests.sh` — Current script to update

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Tier flags work correctly
    Tool: Bash
    Steps:
      1. Run: ./tests/run_all_tests.sh --tier integrity --skip-docker --no-fixtures
      2. Assert exit code 0, output contains "integrity" tier run
    Expected Result: Only integrity tests run, pass
    Failure Indicators: Wrong tier runs, or all tiers run
    Evidence: .sisyphus/evidence/task-9-tier-integrity.txt

  Scenario: Default runs integrity + parity
    Tool: Bash
    Steps:
      1. Run: ./tests/run_all_tests.sh --skip-docker --no-fixtures
      2. Assert output mentions both integrity and parity markers
    Expected Result: Two tiers run
    Failure Indicators: Only one tier or all tiers run
    Evidence: .sisyphus/evidence/task-9-default.txt
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `test(parity): add tiered test execution to run_all_tests.sh`
  - Files: `tests/run_all_tests.sh`
  - Pre-commit: `bash -n tests/run_all_tests.sh`

- [x] 10. Update tests/AGENTS.md with New Architecture

  **What to do**:
  - Update `tests/AGENTS.md` to reflect:
    1. New tiered test architecture (integrity / parity / parity_full)
    2. New file: `tests/helpers/comparison.py` — shared comparison module
    3. New file: `tests/test_layer_audit.py` — layer integrity gate
    4. New file: `tests/test_comparison_helper.py` — helper unit tests
    5. New file: `tests/test_edge_cases.py` — schema/range edge cases
    6. Updated tolerance: 0.05 → 0.01
    7. Updated comparison: inner join → outer join + symmetric NaN
    8. Updated commands section with new tier flags
    9. Updated CRITICAL CONSTRAINTS: mention the new hard-fail behavior

  **Must NOT do**:
  - Do NOT add information not reflected in the actual code changes

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Documentation update
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (last task)
  - **Blocks**: F1-F4
  - **Blocked By**: All previous tasks

  **References**:
  - `tests/AGENTS.md` — Current file to update

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: AGENTS.md documents all new files and tiers
    Tool: Bash (grep)
    Steps:
      1. grep "comparison.py" tests/AGENTS.md → match
      2. grep "test_layer_audit" tests/AGENTS.md → match
      3. grep "0.01" tests/AGENTS.md → match
      4. grep "outer join" tests/AGENTS.md → match
      5. grep "integrity" tests/AGENTS.md → match
    Expected Result: All key concepts documented
    Failure Indicators: Any grep returns no match
    Evidence: .sisyphus/evidence/task-10-docs.txt
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `docs(tests): update AGENTS.md with tiered architecture and new test files`
  - Files: `tests/AGENTS.md`
  - Pre-commit: none (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `uv run ruff check tests/` + `uv run mypy tests/`. Review all changed files for: `as any`/`@ts-ignore` equivalents (type: ignore), empty catches, print in tests (should use pytest.fail/pytest.skip), commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Lint [PASS/FAIL] | Type Check [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (comparison helper used consistently across all parity tests). Test edge cases. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Verify NO changes to `src/ohipy/` calculation code. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1**: `test(parity): add shared comparison helper, markers, and layer audit gate` - tests/helpers/comparison.py, tests/conftest.py, tests/test_layer_audit.py
- **Wave 2**: `test(parity): migrate parity tests to 0.01 tolerance with outer-join comparison` - tests/test_r_parity.py, tests/test_parity_full.py, tests/comparative/compare_scores.py
- **Wave 3**: `test(parity): add edge case tests and tiered test runner` - tests/test_edge_cases.py, tests/run_all_tests.sh, tests/AGENTS.md

---

## Success Criteria

### Verification Commands
```bash
uv run pytest tests/test_layer_audit.py -v                    # All 98 layers validated
uv run pytest -m integrity -v                                  # Fast tier passes
uv run pytest -m parity -v                                     # Baseline parity at 0.01
uv run pytest -m parity_full -v                                # All 44 variations at 0.01
uv run ruff check tests/                                       # Lint clean
uv run mypy tests/                                             # Type check clean
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] Outer join comparison used everywhere (no inner joins)
- [ ] Symmetric NaN check implemented
- [ ] 0.01 tolerance enforced
- [ ] 98 layers validated as present + non-empty
- [ ] Dimension-first failure reporting works
- [ ] pytest markers configured correctly
- [ ] No changes to src/ohipy/ calculation code
