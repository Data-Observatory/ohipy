# Learnings

### Final QA Gate Run (2026-04-02)
- `run_all_tests.sh` failed during Phase 3 fixture generation due to fixture lock contention.
- Full logs captured under `.sisyphus/evidence/final-qa/` for both runs.

### Task 2 Compliance Gap Fix (2026-04-02)
- Fixed `tests/parity/setup_fixtures.py` idempotency logic to check both file existence AND non-empty content.
- Modified `generate_fixture()` skip condition: `fixture_path.exists() and not overwrite and not force_regenerate and fixture_path.stat().st_size > 0`
- Empty fixtures now regenerate instead of skipping (fixes F1 compliance finding #2).

### F4 Scope Fidelity Check (2026-04-02)
- Current working tree scope matches expected file set; no `src/ohipy/` changes and no new test files detected.
- Noted Task 3 requirement gap: `run_all_tests.sh` lacks explicit summary of total tests/passed/failed/skipped.

### F3 Final QA Evidence Review (2026-04-02)
- `final-qa/run1.log` shows 44 fixtures generated, pytest collected 73 items, 73 passed, exit OK.
- `final-qa/run2.log` shows all 44 fixtures skipped (idempotent), pytest collected 73 items, 73 passed, exit OK.
- Parity suite confirmed 44/44 pass from `test_parity_full` entries; no skips recorded in either run.

### F2 Code Quality Review (2026-04-02)

**Changed Scope Files (4 total):**
- `tests/parity/r_runner.py` - 276 lines, clean
- `tests/parity/setup_fixtures.py` - 315 lines, clean
- `tests/test_parity_full.py` - 304 lines, clean
- `tests/test_r_parity.py` - 168 lines, clean

**Verification Results:**
- Ruff: 0 errors in changed scope (44 baseline errors in src/)
- Mypy: 0 errors in changed scope (23 baseline errors in src/)
- Anti-patterns: None found (no TODO/FIXME/type:ignore/# noqa)

**Baseline Debt Catalogue:**
- src/ohipy/calculate/__init__.py: I001, N803, N806 (4 errors)
- src/ohipy/config/__init__.py: I001, UP015, E501 (3 errors)
- src/ohipy/dimensions/resilience.py: E501 (1 error)
- src/ohipy/goals/*.py: N802, N806, E501, F401, I001 (multiple per file)
- src/ohipy/types.py: E501 (1 error)
- All 23 mypy errors are missing type annotations in src/ohipy/

**Conclusion:** Plan scope introduced zero regressions. All lint/type issues are pre-existing baseline debt.

### Task 3 Summary Report Patch (2026-04-04)

**What was learned:**
- Pytest summary line format includes `===` decorators: `============================= 73 passed in 39.57s ==============================`
- Initial grep pattern `^[0-9]+ (passed|failed)` failed because the line doesn't start with a digit
- Solution: Remove `^` anchor to match anywhere in line: `grep -E '[0-9]+ (passed|failed)'`
- Using `grep -oE '[0-9]+ passed' | grep -oE '[0-9]+'` robustly extracts counts from varied pytest output formats
- Capturing pytest output to variable while preserving exit code: `output=$(cmd 2>&1) && code=0 || code=$?`

**Implementation pattern for bash pytest parsing:**
```bash
pytest_output=$(uv run pytest tests/ -v 2>&1) && pytest_exit_code=0 || pytest_exit_code=$?
echo "$pytest_output"  # Preserve visible output
summary_line=$(echo "$pytest_output" | grep -E '[0-9]+ (passed|failed)' | tail -1)
TEST_PASSED=$(echo "$summary_line" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo "0")
```

### README Testing Instructions Clarification (2026-04-04)

**User Request**: Update README with crystal clear testing instructions and exact command forms.

**Changes Made**:

1. **Quick Start section** - Combined commands into concise format:
   - `./run_all_tests.sh` - Full suite
   - `./run_all_tests.sh --skip-docker --no-fixtures` - Smoke test
   - `uv run pytest tests/ -v` - All tests
   - `uv run pytest tests/ -v --ignore=tests/test_parity_full.py --ignore=tests/test_r_parity.py` - Unit tests only

2. **Baseline Parity section** - Added AUTO_GENERATE command:
   - `OHI_AUTO_GENERATE_FIXTURES=1 uv run pytest tests/test_r_parity.py -v`

3. **Comprehensive Parity section** - Added AUTO_GENERATE command:
   - `OHI_AUTO_GENERATE_FIXTURES=1 uv run pytest tests/test_parity_full.py -v`

**Commands verified**:
- run_all_tests.sh exists and supports --skip-docker and --no-fixtures flags
- Unit tests collected 29 items with full pytest
- Baseline parity test has 1 test collected
- Comprehensive parity test has 44 tests collected
- AUTO_GENERATE behavior works correctly for both test files

### Documentation Review (2026-04-04)

**Testing Section Gaps Identified:**

1. **Missing run_all_tests.sh coverage** - Bash orchestrator not mentioned
   - Provides automated Docker checks, fixture generation, Python scores, pytest
   - Supports --skip-docker and --no-fixtures flags
   - Should be the primary testing documentation entry

2. **Incomplete parity test documentation**
   - test_r_parity.py (baseline) not mentioned in README
   - Only test_parity_full.py documented
   - Difference unclear: baseline (1 test) vs comprehensive (44 tests)

3. **AUTO_GENERATE behavior not explained**
   - Critical for developers without Docker/R setup
   - test_r_parity.py: Auto-generates if env var set
   - test_parity_full.py: Autouse fixture generates all 44 fixtures
   - run_all_tests.sh sets AUTO_GENERATE_FIXTURES=1 during pytest

4. **Prerequisites confusing**
   - Suggests R fixtures are pre-generated (but they're actually generated)
   - Doesn't explain AUTO_GENERATE workflow
   - Doesn't explain skip behavior vs fixture generation

**Key Commands Identified:**
```bash
# Full pipeline
./run_all_tests.sh
./run_all_tests.sh --skip-docker
./run_all_tests.sh --no-fixtures

# Unit tests only
uv run pytest tests/ -v --ignore=tests/test_parity_full.py

# Baseline parity
uv run pytest tests/test_r_parity.py -v

# Comprehensive parity
uv run pytest tests/test_parity_full.py -v

# Regenerate fixtures
uv run python tests/parity/setup_fixtures.py
```
