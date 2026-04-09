# Parquet Support & Data Decoupling

## TL;DR

> **Quick Summary**: Decouple data from chl/ git submodule into dedicated data/ folder. Add dual CSV/Parquet support for layer loading (prefer Parquet, fallback to CSV). Create minimal test fixtures for package independence.
>
> **Deliverables**:
> - `data/` folder with config CSVs + layer CSVs + layer Parquets
> - Modified `load_layers()` supporting both formats
> - Minimal test fixtures in `tests/fixtures/`
> - Updated documentation
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 5 waves
> **Critical Path**: Task 1 → Task 2 → Task 4 → Task 5 → Task 7

---

## Context

### Original Request
Decouple data from chl/ external R repo into a dedicated data/ folder, add Parquet support for layers (better performance), and create test fixtures so the package is independent.

### Interview Summary
**Key Discussions**:
- Data folder: `data/` (generic name, not versioned)
- Structure: `data/conf/`, `data/layers.csv`, `data/layers/csv/`, `data/layers/parquet/`
- Formats: Keep BOTH CSV and Parquet for layers
- Config files: Keep as CSV only (not Parquet)
- Test fixtures: Create minimal fixtures in `tests/fixtures/`
- chl submodule: KEEP for R comparison scripts

**Research Findings**:
- chl is a git submodule (not gitignored)
- 227 CSV layer files, 6 config CSVs, 1 layers.csv metadata
- Current loading uses `pl.read_csv(path, null_values=["NA"])`
- NaN/null fidelity is critical regression risk

### Metis Review
**Identified Gaps** (addressed):
- Submodule handling: Keep chl/ for R comparison, add data/ for Python
- NaN round-trip: Add verification script with `pd.testing.assert_frame_equal()`
- .xlsx file: Exclude (not referenced in layers.csv)
- Benchmark script: Update to handle branches with/without data/

---

## Work Objectives

### Core Objective
Decouple Python package from chl/ submodule, add Parquet format support for faster loading, create minimal test fixtures.

### Concrete Deliverables
- `data/` folder: conf/, layers.csv, layers/csv/, layers/parquet/
- Modified `src/ohipy/layers/__init__.py` with Parquet support
- `scripts/convert_layers_to_parquet.py` conversion script
- `tests/fixtures/` minimal test data
- Updated config.yaml paths

### Definition of Done
- [ ] `uv run python comparative/compare_scores.py` → SUCCESS (identical scores)
- [ ] `uv run pytest tests/ -v` → all pass
- [ ] Parquet files load correctly with CSV fallback working

### Must Have
- Both CSV and Parquet layer files in data/
- load_layers() prefers Parquet, falls back to CSV
- R parity maintained (scores match R fixture exactly)
- Test fixtures for fast unit tests

### Must NOT Have (Guardrails)
- DO NOT change calculation code (calculate_all.py, goals/, dimensions/)
- DO NOT modify `comparative/scores_2024_r.csv` fixture
- DO NOT change DataFrame column types or NaN handling
- DO NOT add abstraction layers or factory patterns (AI slop)
- DO NOT convert config CSVs to Parquet

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (existing tests + new fixture tests)
- **Framework**: pytest

### QA Policy
Every task includes agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Backend/API**: Use Bash (uv run commands) — Run scripts, verify exit codes, check output

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — data folder creation):
└── Task 1: Create data/ folder structure and copy files [quick]

Wave 2 (After Wave 1 — config + conversion, MAX PARALLEL):
├── Task 2: Update config.yaml paths + verify R parity [quick]
└── Task 3: CSV→Parquet conversion script + execute [quick]

Wave 3 (After Wave 2 — code changes + docs, MAX PARALLEL):
├── Task 4: Modify load_layers() for Parquet support [quick]
└── Task 6: Update benchmark script and documentation [quick]

Wave 4 (After Wave 3 — test fixtures):
└── Task 5: Create test fixtures in tests/fixtures/ [deep]

Wave 5 (After Wave 4 — final verification):
└── Task 7: Final integration verification [quick]

Critical Path: Task 1 → Task 2 → Task 4 → Task 5 → Task 7
Parallel Speedup: ~40% faster than sequential
Max Concurrent: 2 (Waves 2 & 3)
```

### Dependency Matrix

- **1**: — — 2, 3
- **2**: 1 — 4, 6
- **3**: 1 — 4
- **4**: 2, 3 — 5, 7
- **5**: 4 — 7
- **6**: 2 — 7
- **7**: 4, 5, 6 — —

### Agent Dispatch Summary

- **Wave 1**: 1 task → `quick` (git-master skill for atomic commit)
- **Wave 2**: 2 tasks → both `quick`
- **Wave 3**: 2 tasks → both `quick`
- **Wave 4**: 1 task → `deep`
- **Wave 5**: 1 task → `quick`

---

## TODOs

- [x] 1. **Create data/ folder structure and copy files from chl/comunas/**

  **What to do**:
  - Create directories: `data/conf/`, `data/layers/csv/`, `data/layers/parquet/`
  - Copy 6 config CSVs from `chl/comunas/conf/` to `data/conf/`
  - Copy `chl/comunas/layers.csv` to `data/layers.csv`
  - Copy 227 CSV files from `chl/comunas/layers/` to `data/layers/csv/` (exclude .xlsx)
  - Verify file counts match
  - Git add and commit atomically

  **Must NOT do**:
  - DO NOT copy the .xlsx file
  - DO NOT modify any files during copy

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward file copy operations, no logic needed
  - **Skills**: [`git-master`]
    - `git-master`: Will need to stage files and commit atomically

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1 (Sequential)
  - **Blocks**: Tasks 2, 3
  - **Blocked By**: None (can start immediately)

  **References**:
  - `src/ohipy/config/config.yaml:17-32` - Current path configuration showing chl/comunas structure
  - `chl/comunas/layers.csv` - Layer metadata file listing all 227 layer files

  **Acceptance Criteria**:
  - [ ] `ls data/conf/*.csv | wc -l` → outputs `6`
  - [ ] `ls data/layers/csv/*.csv | wc -l` → outputs `227`
  - [ ] `test -f data/layers.csv && echo "exists"` → outputs `exists`
  - [ ] `test -d data/layers/parquet && echo "exists"` → outputs `exists`
  - [ ] `diff chl/comunas/conf/goals.csv data/conf/goals.csv` → no output (identical)

  **QA Scenarios**:
  ```
  Scenario: File structure verification
    Tool: Bash
    Steps:
      1. ls data/conf/*.csv | wc -l
      2. ls data/layers/csv/*.csv | wc -l
      3. test -f data/layers.csv
    Expected Result: 6 config files, 227 layer files, layers.csv exists
    Evidence: .sisyphus/evidence/task-01-file-structure.txt
  ```

  **Commit**: YES
  - Message: `feat: create data/ folder structure with files from chl/comunas/`
  - Files: `data/` (entire directory)

- [x] 2. **Update config.yaml paths from chl/comunas to data/ and verify R parity**

  **What to do**:
  - Edit `src/ohipy/config/config.yaml` paths section:
    - `assessment_dir: "chl/comunas"` → `"data"`
    - `conf_dir: "chl/comunas/conf"` → `"data/conf"`
    - `goals_csv: "chl/comunas/conf/goals.csv"` → `"data/conf/goals.csv"`
    - Same pattern for all 6 config CSV paths
    - `layers_dir: "chl/comunas/layers"` → `"data/layers/csv"`
    - `layers_csv: "chl/comunas/layers.csv"` → `"data/layers.csv"`
  - Run `uv run python scripts/run_python_scores.py`
  - Run `uv run python comparative/compare_scores.py`
  - Git commit

  **Must NOT do**:
  - DO NOT change any other config values (constants, element_mappings, etc.)
  - DO NOT proceed if compare_scores.py fails

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single file edit with exact replacements, plus verification commands
  - **Skills**: []
    - No specialized skills needed for YAML editing

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 3)
  - **Parallel Group**: Wave 2 (with Task 3)
  - **Blocks**: Tasks 4, 6
  - **Blocked By**: Task 1

  **References**:
  - `src/ohipy/config/config.yaml:17-32` - Paths section to update
  - `src/ohipy/config/__init__.py:46-68` - How paths are resolved and used
  - `src/ohipy/layers/__init__.py:21-23` - How layers_dir and layers_csv are loaded

  **Acceptance Criteria**:
  - [ ] `uv run python scripts/run_python_scores.py` → exits 0
  - [ ] `uv run python comparative/compare_scores.py` → exits 0 with SUCCESS
  - [ ] `grep "chl/comunas" src/ohipy/config/config.yaml | wc -l` → outputs `0`
  - [ ] `grep "data/" src/ohipy/config/config.yaml | wc -l` → outputs at least `10`

  **QA Scenarios**:
  ```
  Scenario: R parity verification after config change
    Tool: Bash
    Steps:
      1. uv run python scripts/run_python_scores.py
      2. uv run python comparative/compare_scores.py
    Expected Result: SUCCESS with max difference inside tolerance
    Failure Indicators: Any non-zero exit code, "FAILURE" in output
    Evidence: .sisyphus/evidence/task-02-r-parity.txt
  ```

  **Commit**: YES
  - Message: `refactor: update config.yaml paths from chl/comunas to data/`
  - Files: `src/ohipy/config/config.yaml`
  - Pre-commit: `uv run python comparative/compare_scores.py`

- [x] 3. **Create CSV→Parquet conversion script and execute**

  **What to do**:
  - Create `scripts/convert_layers_to_parquet.py`:
    - Read `data/layers.csv` to get list of layers and filenames
    - For each layer CSV in `data/layers/csv/`:
      - `df = pl.read_csv(csv_path, null_values=["NA"])`
      - `df.write_parquet(parquet_path)` (default snappy compression)
      - Verify: `pd.testing.assert_frame_equal(pl.read_parquet(parquet_path).to_pandas(), pl.read_csv(csv_path, null_values=["NA"]).to_pandas())`
    - Print summary: N files converted, N verified
  - Run the script
  - Verify file count matches
  - Git add Parquet files and script, commit

  **Must NOT do**:
  - DO NOT use `pd.read_csv()` for conversion (must use polars for consistency)
  - DO NOT skip the round-trip verification
  - DO NOT proceed if any verification fails

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward script with clear pattern, polars API is simple
  - **Skills**: []
    - No specialized skills needed for data engineering script

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 2)
  - **Parallel Group**: Wave 2 (with Task 2)
  - **Blocks**: Task 4
  - **Blocked By**: Task 1

  **References**:
  - `src/ohipy/layers/__init__.py:44-47` - Current CSV loading pattern with `pl.read_csv(..., null_values=["NA"])`
  - `data/layers.csv` - Metadata file listing all layer filenames (created in Task 1)
  - Polars docs: `pl.read_parquet()`, `df.write_parquet()` - Parquet I/O

  **Acceptance Criteria**:
- [ ] `uv run python scripts/convert_layers_to_parquet.py` → exits 0 with no assertion errors
- [ ] `ls data/layers/parquet/*.parquet | wc -l` → matches CSV count (227)
  - [ ] Script prints verification success for each file

  **QA Scenarios**:
  ```
  Scenario: Parquet round-trip fidelity
    Tool: Bash
    Steps:
      1. uv run python scripts/convert_layers_to_parquet.py 2>&1 | tee conversion.log
      2. grep -c "verified" conversion.log
      3. ls data/layers/parquet/*.parquet | wc -l
    Expected Result: All 227 files converted and verified
    Failure Indicators: AssertionError, "FAILED" in output, count mismatch
    Evidence: .sisyphus/evidence/task-03-parquet-conversion.txt
  ```

  **Commit**: YES
  - Message: `feat: add CSV→Parquet conversion script and generate Parquet layer files`
  - Files: `scripts/convert_layers_to_parquet.py`, `data/layers/parquet/*.parquet`

- [x] 4. **Modify load_layers() to prefer Parquet with CSV fallback**

  **What to do**:
  - In `src/ohipy/layers/__init__.py`, after `layers_dir` is resolved:
    - Add `parquet_dir = layers_dir.parent / 'parquet'` (e.g., `data/layers/parquet/`)
  - In the layer loading loop, before CSV check:
    - Add `parquet_path = parquet_dir / (Path(filename).stem + '.parquet')`
    - Add `if parquet_path.exists(): layer_df = pl.read_parquet(parquet_path).to_pandas()`
    - Change existing CSV check to `elif layer_path.exists():`
  - Update docstring to mention Parquet support
  - Run `uv run python comparative/compare_scores.py`
  - Run `uv run ruff check src/ohipy/layers/` and `uv run mypy src/ohipy/layers/`
  - Git commit

  **Must NOT do**:
  - DO NOT change any calculation logic
  - DO NOT change the return type or structure
  - DO NOT add logging or progress bars
  - DO NOT modify `select_layers_data()` function

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: ~10 lines of code change in one file with clear pattern
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 6)
  - **Parallel Group**: Wave 3 (with Task 6)
  - **Blocks**: Tasks 5, 7
  - **Blocked By**: Tasks 2, 3

  **References**:
  - `src/ohipy/layers/__init__.py:40-51` - Current layer loading loop to modify
  - `src/ohipy/layers/__init__.py:21-23` - How layers_dir is resolved from config
  - Polars docs: `pl.read_parquet()` - Parquet reading API

  **Acceptance Criteria**:
  - [ ] `uv run python scripts/run_python_scores.py` → exits 0
  - [ ] `uv run python comparative/compare_scores.py` → exits 0 with SUCCESS
  - [ ] `uv run ruff check src/ohipy/layers/__init__.py` → exits 0
  - [ ] `uv run mypy src/ohipy/layers/__init__.py` → exits 0

  **QA Scenarios**:
  ```
  Scenario: Parquet preference verification
    Tool: Bash
    Steps:
      1. mv data/layers/csv data/layers/csv_backup
      2. uv run python scripts/run_python_scores.py
      3. uv run python comparative/compare_scores.py
      4. mv data/layers/csv_backup data/layers/csv
    Expected Result: Scores calculated successfully using Parquet files
    Failure Indicators: FileNotFoundError for CSV files (means Parquet not being used)
    Evidence: .sisyphus/evidence/task-04-parquet-preference.txt

  Scenario: CSV fallback verification
    Tool: Bash
    Steps:
      1. mv data/layers/parquet data/layers/parquet_backup
      2. uv run python scripts/run_python_scores.py
      3. uv run python comparative/compare_scores.py
      4. mv data/layers/parquet_backup data/layers/parquet
    Expected Result: Scores calculated successfully using CSV fallback
    Failure Indicators: FileNotFoundError for Parquet files with no CSV fallback
    Evidence: .sisyphus/evidence/task-04-csv-fallback.txt
  ```

  **Commit**: YES
  - Message: `feat: load_layers() prefers Parquet files with CSV fallback`
  - Files: `src/ohipy/layers/__init__.py`
  - Pre-commit: `uv run python comparative/compare_scores.py`

- [x] 5. **Create minimal test fixtures in tests/fixtures/**

  **What to do**:
  - Create `tests/fixtures/` directory structure:
    - `tests/fixtures/conf/` - Copy all 6 config CSVs (small, keep all)
    - `tests/fixtures/layers.csv` - Subset with only needed layers
    - `tests/fixtures/layers/csv/` - Subset of layer CSVs
    - `tests/fixtures/layers/parquet/` - Parquet versions of subset
    - `tests/fixtures/config.yaml` - Fixture-relative paths
  - Select minimal layer subset:
    - `regions_list.csv` (spatial, required)
    - FIS goal layers: `fis_b_bmsy_chl2024.csv`, `fis_meancatch_chl2024.csv`
    - Check `pressures_matrix.csv` and `resilience_matrix.csv` for required P/R layers
  - Create subset `layers.csv` referencing only selected files
  - Copy corresponding CSV and Parquet files
  - Create `tests/fixtures/config.yaml` with fixture-relative paths
  - Add `fixture_config` and `fixture_layers` fixtures to `conftest.py`
  - Keep existing fixtures unchanged
  - Git commit

  **Must NOT do**:
  - DO NOT modify existing conftest.py fixtures
  - DO NOT include all 227 layers (must be minimal subset)
  - DO NOT create fixtures larger than 1MB total

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Requires understanding which layers are needed for which goals, cross-referencing matrices
  - **Skills**: []
    - No specialized skills needed but requires deep reasoning

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (Sequential)
  - **Blocks**: Task 7
  - **Blocked By**: Task 4

  **References**:
  - `data/conf/pressures_matrix.csv` - Maps pressure layers to goals
  - `data/conf/resilience_matrix.csv` - Maps resilience layers to goals
  - `tests/conftest.py` - Existing fixture pattern to follow
  - `src/ohipy/goals/fis.py` - FIS goal implementation showing required layers

  **Acceptance Criteria**:
  - [ ] `test -d tests/fixtures/conf && echo "exists"` → outputs `exists`
  - [ ] `test -d tests/fixtures/layers/csv && echo "exists"` → outputs `exists`
  - [ ] `uv run pytest tests/ -v` → all existing tests still pass
  - [ ] `du -sh tests/fixtures/` → less than 1MB

  **QA Scenarios**:
  ```
  Scenario: Test fixtures load correctly
    Tool: Bash
    Steps:
      1. uv run python -c "from ohipy.config import load_config; c=load_config('tests/fixtures/config.yaml'); print(c['config']['paths']['layers_dir'])"
      2. ls tests/fixtures/layers/csv/*.csv | wc -l
    Expected Result: Config loads, layers directory accessible
    Evidence: .sisyphus/evidence/task-05-fixtures-load.txt
  ```

  **Commit**: YES
  - Message: `feat: add minimal test fixtures for fast unit testing`
  - Files: `tests/fixtures/`, `tests/conftest.py`

- [x] 6. **Update benchmark script and documentation**

  **What to do**:
  - Update `benchmarks/benchmark_branches.py`:
    - Modify `_ensure_chl_data()` to also check for `data/` directory in worktrees
    - For branches with `data/conf/goals.csv` exists, skip symlink
    - For old branches (main, opt1), keep existing chl/ symlink behavior
  - Update `README.md`:
    - Update setup section: data/ is now included in repo
    - Keep `git clone chl` instructions for R comparison only
    - Mark "move auxiliary files from ohi/cl" TODO as done
  - Update `AGENTS.md`:
    - Update STRUCTURE section to show `data/`
    - Update NOTES section about chl/ requirement
    - Update COMMANDS section if needed
  - Update `benchmarks/README.md` chl/ section
  - Git commit

  **Must NOT do**:
  - DO NOT remove chl/ submodule documentation (still needed for R comparison)
  - DO NOT break backward compatibility with old branches

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Documentation updates and minor script modification
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 4)
  - **Parallel Group**: Wave 3 (with Task 4)
  - **Blocks**: Task 7
  - **Blocked By**: Task 2

  **References**:
  - `benchmarks/benchmark_branches.py:57-74` - Current `_ensure_chl_data()` function
  - `README.md` - Setup instructions section
  - `AGENTS.md` - Project documentation

  **Acceptance Criteria**:
  - [ ] `uv run python benchmarks/benchmark_branches.py --branches opt2 --warmups 0 --iterations 1` → exits 0
  - [ ] `grep "data/" README.md | wc -l` → greater than 0
  - [ ] `grep "data/" AGENTS.md | wc -l` → greater than 0

  **QA Scenarios**:
  ```
  Scenario: Benchmark script handles new data/ folder
    Tool: Bash
    Steps:
      1. uv run python -c "from benchmarks.benchmark_branches import _ensure_chl_data; print('OK')"
    Expected Result: Script imports successfully
    Evidence: .sisyphus/evidence/task-06-benchmark.txt
  ```

  **Commit**: YES
  - Message: `docs: update documentation and benchmark script for data/ migration`
  - Files: `benchmarks/benchmark_branches.py`, `README.md`, `AGENTS.md`, `benchmarks/README.md`

- [x] 7. **Final integration verification**

  **What to do**:
  - Run complete verification suite:
    - `uv run ruff check src/`
    - `uv run mypy src/`
    - `uv run pytest tests/ -v`
    - `uv run python scripts/run_python_scores.py`
    - `uv run python comparative/compare_scores.py`
  - Verify Parquet preference: rename CSV dir, confirm Parquet loads
  - Verify CSV fallback: rename Parquet dir, confirm CSV loads
  - No commit (verification only)

  **Must NOT do**:
  - DO NOT make any code changes
  - DO NOT proceed if any verification fails

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Running commands and verifying output
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5 (Sequential, Final)
  - **Blocks**: None
  - **Blocked By**: Tasks 4, 5, 6

  **References**:
  - All previous tasks for verification commands

  **Acceptance Criteria**:
  - [ ] `uv run ruff check src/` → exits 0
  - [ ] `uv run mypy src/` → exits 0
  - [ ] `uv run pytest tests/ -v` → all tests pass
  - [ ] `uv run python scripts/run_python_scores.py` → exits 0
  - [ ] `uv run python comparative/compare_scores.py` → SUCCESS with same max diff as before

  **QA Scenarios**:
  ```
  Scenario: Complete verification suite
    Tool: Bash
    Steps:
      1. uv run ruff check src/ 2>&1 | tee ruff.log
      2. uv run mypy src/ 2>&1 | tee mypy.log
      3. uv run pytest tests/ -v 2>&1 | tee pytest.log
      4. uv run python scripts/run_python_scores.py 2>&1 | tee scores.log
      5. uv run python comparative/compare_scores.py 2>&1 | tee compare.log
      6. grep "SUCCESS" compare.log
    Expected Result: All commands exit 0, SUCCESS in compare output
    Failure Indicators: Any non-zero exit code, "FAILURE" or errors in output
    Evidence: .sisyphus/evidence/task-07-final-verification.txt

  Scenario: Format preference test
    Tool: Bash
    Steps:
      1. mv data/layers/csv data/layers/csv_backup
      2. uv run python comparative/compare_scores.py
      3. mv data/layers/csv_backup data/layers/csv
      4. mv data/layers/parquet data/layers/parquet_backup
      5. uv run python comparative/compare_scores.py
      6. mv data/layers/parquet_backup data/layers/parquet
    Expected Result: Both tests pass (Parquet preference, CSV fallback)
    Evidence: .sisyphus/evidence/task-07-format-test.txt
  ```

  **Commit**: NO (verification only)

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Verify all "Must Have" implemented, all "Must NOT Have" absent. Check evidence files. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check src/`, `mypy src/`, `pytest tests/`. Review for type issues, lint errors.
  Output: `Lint [PASS/FAIL] | Types [PASS/FAIL] | Tests [N/N pass] | VERDICT`

- [x] F3. **R Parity Verification** — `unspecified-high`
  Run `uv run python comparative/compare_scores.py`. Verify max difference matches pre-migration value.
  Output: `R Parity [PASS/FAIL] | Max Diff [value] | VERDICT`

- [x] F4. **Format Fallback Test** — `deep`
  Test Parquet preference (rename CSV dir, verify Parquet loads). Test CSV fallback (rename Parquet dir, verify CSV loads).
  Output: `Parquet [PASS/FAIL] | CSV Fallback [PASS/FAIL] | VERDICT`

---

## Commit Strategy

Atomic commits in strict order:

1. `feat: create data/ folder structure with files from chl/comunas/`
2. `refactor: update config.yaml paths from chl/comunas to data/`
3. `feat: add CSV→Parquet conversion script and generate Parquet files`
4. `feat: load_layers() prefers Parquet files with CSV fallback`
5. `feat: add minimal test fixtures for fast unit testing`
6. `docs: update documentation and benchmark script for data/ migration`

---

## Success Criteria

### Verification Commands
```bash
uv run python comparative/compare_scores.py  # Expected: SUCCESS with same max diff
uv run pytest tests/ -v                       # Expected: all pass
uv run ruff check src/ && uv run mypy src/    # Expected: clean
ls data/layers/parquet/*.parquet | wc -l      # Expected: 227
```

### Final Checklist
- [x] All "Must Have" present
- [x] All "Must NOT Have" absent
- [x] All tests pass
- [x] R parity maintained
- [x] Parquet preference works
- [x] CSV fallback works
