# Full Test Suite: Automated 44-Parity Test Runner

## TL;DR

> **Quick Summary**: Create a single `run_all_tests.sh` script that orchestrates the full test suite end-to-end — building the Docker image if needed, cloning `chl/` if missing, generating all 44 R fixtures, running Python scores, and executing the complete pytest suite with zero skips and zero manual prerequisites.
>
> **Deliverables**:
> - `run_all_tests.sh` — single executable script for the full pipeline
> - Updated `tests/parity/setup_fixtures.py` — idempotent fixture generation with lock protection
> - Updated `tests/parity/r_runner.py` — robust Docker interaction with UID/GID handling
> - Updated `tests/test_parity_full.py` — env-var-gated auto-generation, no skips in CI mode
> - Updated `tests/test_r_parity.py` — auto-generate baseline R fixture when env-var set
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4 → Task 5

---

## Context

### Original Request
User wants a fully automated testing suite. No skips, no placeholders, a single executable shell script (`run_all_tests.sh`) that runs the 44 parity tests, creates simulated data from the R Docker image, and creates all needed files if they're not already present. No manual prerequisites.

### Interview Summary
**Key Discussions**:
- Existing infrastructure is solid: `setup_fixtures.py`, `data_modifiers.py`, `r_runner.py` all exist and work
- The gap is orchestration: no single script ties everything together, and tests skip when fixtures are absent
- User explicitly wants to update existing files, not create new test modules
- Docker image `ohicore-r-env` is already built locally; `chl/` repo is already cloned

**Research Findings**:
- `tests/test_parity_full.py` has `pytest.skip()` on missing fixtures — must be removed in CI mode
- `tests/test_r_parity.py` has `pytest.skip()` on missing R fixture — must be removed in CI mode
- `setup_fixtures.py` already handles: noise generation, scenario preparation, Docker R execution, fixture saving
- `r_runner.py` has `docker_available()` check and basic error handling — needs UID/GID hardening
- No `comparative/cache/` or `comparative/fixtures/` directories exist yet (will be created by script)

### Metis Review
**Identified Gaps** (addressed):
- Breaking normal `pytest` workflow: Mitigated by env-var gating (`OHI_AUTO_GENERATE_FIXTURES=1`)
- Non-deterministic noise: Mitigated by fixed seed (already seed=42 in code)
- Docker file permissions: Mitigated by `--user $(id -u):$(id -g)` flag
- Race conditions in fixture gen: Mitigated by lockfile in setup_fixtures.py
- Idempotency: Mitigated by "skip if exists" logic already in setup_fixtures.py

---

## Work Objectives

### Core Objective
Create a fully automated, zero-manual-prerequisites test pipeline that runs all 44 parity tests plus all unit tests via a single shell script.

### Concrete Deliverables
- `run_all_tests.sh` at project root — executable, idempotent, handles all prerequisites
- Updated existing test/parity files with env-var-gated auto-generation

### Definition of Done
- [ ] `./run_all_tests.sh` exits 0 from a clean state (no cache, no fixtures)
- [ ] `pytest` reports 44 passed, 0 skipped for `test_parity_full.py`
- [ ] `pytest` reports passed, 0 skipped for `test_r_parity.py`
- [ ] All unit tests pass
- [ ] Running `./run_all_tests.sh` a second time also exits 0 (idempotent)
- [ ] Plain `uv run pytest tests/` still works (unit tests pass, parity tests skip gracefully without Docker)

### Must Have
- Single `run_all_tests.sh` that handles everything
- Zero skips in CI/script mode
- Idempotent fixture generation (safe to re-run)
- Clear error messages on failure (Docker unavailable, image missing, clone fails, etc.)
- Normal `uv run pytest` workflow preserved for developers without Docker

### Must NOT Have (Guardrails)
- NO new test files (update existing only)
- NO changes to calculation code (`src/ohipy/`)
- NO CI/CD config (out of scope)
- NO changes to R Docker image or Dockerfile
- NO changes to `comparative/scores_2024_r.csv` (R reference fixture)
- NO refactoring of existing unit tests
- NO additional pytest plugins or test dependencies

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: Tests-after (the test files ARE the deliverable)
- **Framework**: pytest

### QA Policy
Every task includes agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Shell script**: Use Bash — execute script, check exit code, grep output
- **Python modules**: Use Bash — run pytest, verify pass/skip counts
- **Fixture files**: Use Bash — check file existence, line counts, content

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — can start immediately):
├── Task 1: Harden r_runner.py for production use [quick]
├── Task 2: Add lockfile + idempotency to setup_fixtures.py [unspecified-high]
└── Task 3: Create run_all_tests.sh shell script [unspecified-high]

Wave 2 (Test updates — after Wave 1):
├── Task 4: Update test_parity_full.py — remove skips, add env-var gate [quick]
└── Task 5: Update test_r_parity.py — remove skip, add env-var gate [quick]

Wave FINAL (After ALL tasks — verification):
├── Task F1: Plan compliance audit [oracle]
├── Task F2: Code quality review [unspecified-high]
├── Task F3: Real end-to-end QA [deep]
└── Task F4: Scope fidelity check [deep]
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 3 | 1 |
| 2 | — | 3 | 1 |
| 3 | 1, 2 | F3 | 1 |
| 4 | 2 | F3 | 2 |
| 5 | 1 | F3 | 2 |
| F1 | 3, 4, 5 | user ok | FINAL |
| F2 | 3, 4, 5 | user ok | FINAL |
| F3 | 3, 4, 5 | user ok | FINAL |
| F4 | 3, 4, 5 | user ok | FINAL |

### Agent Dispatch Summary

- **Wave 1**: 3 tasks — T1 `quick`, T2 `unspecified-high`, T3 `unspecified-high`
- **Wave 2**: 2 tasks — T4 `quick`, T5 `quick`
- **FINAL**: 4 tasks — F1 `oracle`, F2 `unspecified-high`, F3 `deep`, F4 `deep`

---

## TODOs

- [x] 1. Harden `tests/parity/r_runner.py` for Production Use

  **What to do**:
  - Add `--user $(id -u):$(id -g)` to Docker run command to prevent root-owned output files
  - Add timeout to Docker subprocess (300 seconds per R calculation)
  - Improve error messages: include Docker command, exit code, and last 50 lines of stderr
  - Add `build_docker_image()` function that runs `docker build -t ohicore-r-env comparative/images/R/` if image not found
  - Add `ensure_docker_image()` that checks existence and calls build if missing
  - Add `check_chl_repo()` that verifies `chl/comunas/conf/` exists, returns clear error if missing
  - Keep existing `docker_available()` function but add `docker_daemon_running()` check (docker info)
  - Keep all existing function signatures and return types unchanged

  **Must NOT do**:
  - Do NOT change function signatures (backward compatible)
  - Do NOT add new dependencies
  - Do NOT modify `comparative/images/R/Dockerfile`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Task 3
  - **Blocked By**: None

  **References**:

  **Pattern References** (existing code to follow):
  - `tests/parity/r_runner.py:17-26` - Current `docker_available()` check pattern
  - `tests/parity/r_runner.py:29-116` - Current `run_r_calculation()` with subprocess.run pattern
  - `tests/parity/r_runner.py:90-106` - Docker subprocess.run call to extend with --user flag

  **API/Type References** (contracts to preserve):
  - `tests/parity/r_runner.py:17` - `docker_available() -> bool` signature must remain
  - `tests/parity/r_runner.py:29` - `run_r_calculation(conf_dir, layers_dir, output_csv) -> pl.DataFrame | None` signature must remain
  - `tests/parity/r_runner.py:119` - `run_r_with_temporary_data(conf_dir, layers_dir) -> pl.DataFrame | None` signature must remain

  **External References**:
  - Docker `--user` flag: https://docs.docker.com/engine/reference/run/#user
  - Python `subprocess.run(timeout=)`: https://docs.python.org/3/library/subprocess.html#subprocess.run

  **WHY Each Reference Matters**:
  - `r_runner.py:17-26`: The existing docker check pattern to extend, not replace
  - `r_runner.py:90-106`: The exact subprocess call to add --user flag to
  - Function signatures: setup_fixtures.py imports these functions, changing signatures breaks it

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Docker image check detects missing image
    Tool: Bash
    Preconditions: ohicore-r-env image exists (current state)
    Steps:
      1. Run: uv run python -c "from tests.parity.r_runner import docker_available; print(docker_available())"
      2. Assert output contains "True"
    Expected Result: Returns True when image exists
    Evidence: .sisyphus/evidence/task-1-docker-check.txt

  Scenario: Docker daemon check works
    Tool: Bash
    Preconditions: Docker daemon is running
    Steps:
      1. Run: uv run python -c "from tests.parity.r_runner import docker_available; print(docker_available())"
      2. Assert exit code 0
    Expected Result: No import error, function callable
    Evidence: .sisyphus/evidence/task-1-daemon-check.txt
  ```

  **Commit**: YES
  - Message: `test(parity): harden r_runner.py with UID/GID and error handling`
  - Files: `tests/parity/r_runner.py`

- [x] 2. Add Lockfile and Idempotency to `tests/parity/setup_fixtures.py`

  **What to do**:
  - Add file-based lock mechanism using `comparative/fixtures/.lock` to prevent parallel fixture generation
  - Use `fcntl.flock()` (Linux) for lock acquisition with non-blocking mode
  - Add `acquire_lock()` and `release_lock()` context manager functions
  - In `generate_fixture()`: acquire lock before prepare_scenario, release after copy
  - In `generate_noisy_layers()`: acquire lock before writing cache
  - Add `--force-regenerate` CLI flag that deletes existing fixtures and regenerates (separate from existing `--overwrite`)
  - Ensure `generate_fixture()` is truly idempotent: if fixture exists and is non-empty, skip (already done, just verify)
  - Add progress reporting: print `[N/44]` during generation
  - Add summary report at end: total generated, total skipped (already existed), total failed
  - Keep all existing CLI args (`--check`, `--overwrite`, `--datasets`, `--variations`) unchanged

  **Must NOT do**:
  - Do NOT change existing CLI argument names or defaults
  - Do NOT change the fixture directory structure (`comparative/fixtures/{dataset}/{variation}.csv`)
  - Do NOT change the noise generation logic (seed=42 must remain)
  - Do NOT add new dependencies beyond stdlib

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Task 3
  - **Blocked By**: None

  **References**:

  **Pattern References** (existing code to follow):
  - `tests/parity/setup_fixtures.py:46-57` - Current `generate_noisy_layers()` with "skip if exists" pattern
  - `tests/parity/setup_fixtures.py:174-190` - Current `generate_fixture()` with "skip if exists" pattern
  - `tests/parity/setup_fixtures.py:193-203` - Current `generate_all_fixtures()` with success/failure counters

  **API/Type References** (contracts to preserve):
  - `tests/parity/setup_fixtures.py:60` - `prepare_scenario(dataset, variation)` called by test_parity_full pattern
  - `tests/parity/setup_fixtures.py:131` - `run_r_calculation(output_csv)` signature
  - CLI args: `--check`, `--overwrite`, `--generate-noise-only`, `--datasets`, `--variations`

  **External References**:
  - Python `fcntl.flock()`: https://docs.python.org/3/library/fcntl.html

  **WHY Each Reference Matters**:
  - `generate_noisy_layers` and `generate_fixture`: Already have "skip if exists" — lock must wrap these
  - CLI args: The shell script will call this file, must not break existing interface

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Lock prevents concurrent fixture generation
    Tool: Bash
    Preconditions: No lock file exists
    Steps:
      1. Create lock dir: mkdir -p comparative/fixtures
      2. Run: uv run python -c "
import fcntl, time
lock = open('comparative/fixtures/.lock', 'w')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
print('Lock acquired')
time.sleep(5)
" &
      3. Immediately run: uv run python tests/parity/setup_fixtures.py --check
      4. Wait for background process
    Expected Result: Lock file mechanism exists in code (verify via grep for fcntl)
    Evidence: .sisyphus/evidence/task-2-lockfile.txt

  Scenario: Idempotent fixture generation
    Tool: Bash
    Preconditions: comparative/fixtures/ does NOT exist
    Steps:
      1. Run: uv run python tests/parity/setup_fixtures.py --datasets original --variations baseline
      2. Verify: ls comparative/fixtures/original/baseline.csv
      3. Run same command again
      4. Verify: file still exists, no error
    Expected Result: Both runs succeed, fixture exists, second run says "exists"
    Evidence: .sisyphus/evidence/task-2-idempotent.txt
  ```

  **Commit**: YES
  - Message: `test(parity): add lockfile and idempotency to setup_fixtures.py`
  - Files: `tests/parity/setup_fixtures.py`

- [x] 3. Create `run_all_tests.sh` Shell Script

  **What to do**:
  - Create `run_all_tests.sh` at project root with `#!/usr/bin/env bash` and `set -euo pipefail`
  - Script phases (in order):
    1. **Preflight checks**: Docker available? Docker daemon running? `ohicore-r-env` image exists? If not, build it from `comparative/images/R/`. If build fails, print clear error and exit 1.
    2. **Repo check**: `chl/` directory exists? If not, `git clone --depth 1 https://github.com/OHI-Science/chl`. If clone fails, print clear error and exit 1.
    3. **Generate noisy layers**: `uv run python tests/parity/setup_fixtures.py --generate-noise-only`
    4. **Generate R fixtures**: `OHI_AUTO_GENERATE_FIXTURES=1 uv run python tests/parity/setup_fixtures.py`. If any fixture fails, exit 1.
    5. **Generate Python scores**: `uv run python scripts/run_python_scores.py`
    6. **Run full pytest**: `OHI_AUTO_GENERATE_FIXTURES=1 uv run pytest tests/ -v --tb=short`
    7. **Report**: Print summary (total tests, passed, failed, skipped)
  - Add `--skip-docker` flag to skip Docker-dependent tests (for offline/local testing)
  - Add `--no-fixtures` flag to skip fixture generation if already done
  - Color-coded output (green=ok, red=fail, yellow=warning) using ANSI codes
  - Each phase prints a banner: `=== Phase N: Description ===`
  - Time each phase and print duration
  - Exit 0 if all tests pass, exit 1 if any fail
  - Make executable: `chmod +x run_all_tests.sh`

  **Must NOT do**:
  - Do NOT install new packages
  - Do NOT modify any Python source files
  - Do NOT create Python test files
  - Do NOT use non-standard tools (only bash, docker, git, uv)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 1, 2 patterns)
  - **Parallel Group**: Wave 1 (sequential after T1/T2 understanding)
  - **Blocks**: Tasks 4, 5 (via env-var contract), F3
  - **Blocked By**: Tasks 1, 2 (must understand their APIs)

  **References**:

  **Pattern References** (existing code to follow):
  - `tests/parity/setup_fixtures.py:221-247` - CLI entry point with argparse pattern to call
  - `tests/parity/r_runner.py:17-26` - Docker availability check pattern (script should duplicate in bash)
  - `comparative/images/R/Dockerfile` - Docker build context path

  **API/Type References** (contracts to call correctly):
  - `tests/parity/setup_fixtures.py` CLI: `--check`, `--overwrite`, `--generate-noise-only`, `--datasets`, `--variations`
  - `scripts/run_python_scores.py` - generates `comparative/scores_2024_py.csv`
  - `tests/test_parity_full.py` - expects `OHI_AUTO_GENERATE_FIXTURES=1` env var (set by Task 4)

  **External References**:
  - Bash `set -euo pipefail`: Standard strict mode
  - ANSI color codes: `\033[0;32m` green, `\033[0;31m` red, `\033[0;33m` yellow

  **WHY Each Reference Matters**:
  - `setup_fixtures.py` CLI: The script's main orchestration target, must call correct flags
  - `r_runner.py`: Provides the Docker patterns the script needs to replicate in bash for preflight
  - `run_python_scores.py`: Must run this to generate py scores for test_r_parity.py

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Script runs end-to-end from clean state
    Tool: Bash
    Preconditions: comparative/cache/ and comparative/fixtures/ deleted, Docker running
    Steps:
      1. rm -rf comparative/cache/ comparative/fixtures/
      2. Run: bash run_all_tests.sh 2>&1 | tee /tmp/test-output.txt
      3. Check exit code: echo $?
      4. Grep output for: "44 passed"
      5. Grep output for: "0 skipped"
      6. Verify fixture files: ls comparative/fixtures/*/baseline.csv | wc -l
    Expected Result: Exit code 0, output contains "44 passed, 0 skipped", 4 baseline.csv files
    Failure Indicators: Exit code non-zero, "ERROR" in output, missing fixture files
    Evidence: .sisyphus/evidence/task-3-e2e-clean.txt

  Scenario: Script is idempotent (second run)
    Tool: Bash
    Preconditions: Fixtures already generated from first run
    Steps:
      1. Run: bash run_all_tests.sh 2>&1 | tee /tmp/test-output-2.txt
      2. Check exit code: echo $?
      3. Grep for "exists" or "skipped" in fixture generation phase
    Expected Result: Exit code 0, fixtures reused (not regenerated), tests still pass
    Evidence: .sisyphus/evidence/task-3-idempotent.txt

  Scenario: Script fails clearly when Docker unavailable
    Tool: Bash
    Preconditions: Stop Docker daemon (or mock docker command to fail)
    Steps:
      1. Run: PATH=/usr/bin:/bin bash run_all_tests.sh 2>&1 | head -20
      2. Check exit code (should be non-zero)
      3. Grep for "Docker" in output
    Expected Result: Exit code 1, clear error message mentioning Docker
    Evidence: .sisyphus/evidence/task-3-docker-fail.txt
  ```

  **Commit**: YES
  - Message: `test: add run_all_tests.sh for fully automated test pipeline`
  - Files: `run_all_tests.sh`

- [x] 4. Update `tests/test_parity_full.py` — Remove Skips, Add Env-Var Gate

  **What to do**:
  - Remove the `pytest.skip()` call in `test_parity_full()` when `OHI_AUTO_GENERATE_FIXTURES=1` env var is set
  - When env var IS set and fixture is missing, call `setup_fixtures.generate_fixture(dataset, variation)` to generate it on-demand
  - When env var is NOT set, keep current `pytest.skip()` behavior (preserve normal developer workflow)
  - Add a `pytest.fixture` session-scoped that generates all fixtures upfront when env var is set (to avoid 44 individual Docker runs during test collection)
  - Import `os` at the top for `os.environ.get()`
  - Add `OHI_AUTO_GENERATE_FIXTURES` constant at module level: `AUTO_GEN = os.environ.get("OHI_AUTO_GENERATE_FIXTURES", "") == "1"`
  - Keep all existing constants, helper functions, and parametrize decorators unchanged

  **Must NOT do**:
  - Do NOT change DATASETS, VARIATIONS, TOLERANCE, or other constants
  - Do NOT change the parametrize decorators
  - Do NOT change `_run_py_calculation()` or `_compare_scores()` functions
  - Do NOT add new test functions or test files

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Task 5)
  - **Blocks**: F3
  - **Blocked By**: Task 2

  **References**:

  **Pattern References** (existing code to follow):
  - `tests/test_parity_full.py:194-210` - Current `_all_fixtures_exist()` and `_missing_fixtures()` helpers
  - `tests/test_parity_full.py:218-242` - Current test with skip logic at lines 233-242
  - `tests/parity/setup_fixtures.py:174-191` - `generate_fixture()` function to call for auto-generation

  **API/Type References** (contracts to preserve):
  - `tests/test_parity_full.py:97-99` - `_get_fixture_path(dataset, variation) -> Path`
  - `tests/test_parity_full.py:110-155` - `_run_py_calculation(layers_dir, variation) -> pl.DataFrame`
  - `tests/test_parity_full.py:158-186` - `_compare_scores(py_scores, r_scores, tolerance) -> dict`

  **External References**:
  - pytest env vars: https://docs.pytest.org/en/stable/example/simple.html#pass-different-values-to-a-test-function
  - pytest fixtures: https://docs.pytest.org/en/stable/reference/fixtures.html

  **WHY Each Reference Matters**:
  - Lines 233-242: The exact skip block to gate behind env var
  - `setup_fixtures.py:174-191`: The function to call for on-demand generation
  - Helper functions: Must not change signatures since they're called by the parametrized test

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: No skips with OHI_AUTO_GENERATE_FIXTURES=1
    Tool: Bash
    Preconditions: Fixtures generated (or script run first), env var set
    Steps:
      1. Run: OHI_AUTO_GENERATE_FIXTURES=1 uv run pytest tests/test_parity_full.py -v 2>&1 | tee /tmp/parity-output.txt
      2. Grep output for "44 passed"
      3. Grep output for "0 skipped"
      4. Grep output for "SKIPPED" — should find none
    Expected Result: 44 passed, 0 skipped, no SKIPPED entries
    Evidence: .sisyphus/evidence/task-4-auto-gen.txt

  Scenario: Graceful skip without env var (no Docker required)
    Tool: Bash
    Preconditions: comparative/fixtures/ deleted
    Steps:
      1. Run: uv run pytest tests/test_parity_full.py -v 2>&1 | tee /tmp/parity-skip.txt
      2. Grep output for "44 skipped"
      3. Check exit code is 0 (skips don't fail)
    Expected Result: 44 skipped, 0 failed, exit code 0
    Evidence: .sisyphus/evidence/task-4-graceful-skip.txt

  Scenario: Env var triggers fixture generation if missing
    Tool: Bash
    Preconditions: comparative/fixtures/ deleted
    Steps:
      1. Run: OHI_AUTO_GENERATE_FIXTURES=1 uv run pytest tests/test_parity_full.py -v 2>&1 | head -50
      2. Check that fixture generation happens (logs visible or takes time)
      3. Verify: ls comparative/fixtures/original/baseline.csv exists
    Expected Result: Fixtures generated during test session, tests pass
    Failure Indicators: Tests skip despite env var being set
    Evidence: .sisyphus/evidence/task-4-on-demand-gen.txt
  ```

  **Commit**: YES
  - Message: `test(parity): remove skips from test_parity_full.py, add env-var auto-generation`
  - Files: `tests/test_parity_full.py`

- [x] 5. Update `tests/test_r_parity.py` — Remove Skip, Add Env-Var Gate

  **What to do**:
  - Gate the `pytest.skip()` at line 36 behind the same `OHI_AUTO_GENERATE_FIXTURES` env var
  - When env var IS set and R fixture is missing, auto-generate it by calling Docker Rscript command (same as `comparative/calculate_scores.r` logic)
  - When env var IS set and Python output is missing, auto-generate by running `scripts/run_python_scores.py` via subprocess
  - When env var is NOT set, keep current skip behavior
  - Add a helper `_generate_r_fixture()` that runs the Docker command to produce `comparative/scores_2024_r.csv`
  - Add a helper `_generate_py_scores()` that runs `uv run python scripts/run_python_scores.py`
  - Import `os`, `subprocess` at the top

  **Must NOT do**:
  - Do NOT change TOLERANCE constant
  - Do NOT change the comparison logic (lines 46-88)
  - Do NOT change the diff output logic
  - Do NOT add new test functions

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Task 4)
  - **Blocks**: F3
  - **Blocked By**: Task 1

  **References**:

  **Pattern References** (existing code to follow):
  - `tests/test_r_parity.py:35-36` - The skip line to gate
  - `tests/test_r_parity.py:38-41` - The pytest.fail for missing Python output
  - `comparative/calculate_scores.r:18-48` - R calculation script logic to replicate in Python subprocess
  - `scripts/run_python_scores.py` - Python score generation entry point

  **API/Type References** (contracts to preserve):
  - `tests/test_r_parity.py:16-19` - Constants (COMPARATIVE_DIR, R_FIXTURE, PY_OUTPUT, DIFF_OUTPUT)
  - `tests/test_r_parity.py:23` - `test_python_matches_r()` function signature

  **External References**:
  - subprocess.run: https://docs.python.org/3/library/subprocess.html

  **WHY Each Reference Matters**:
  - Line 35-36: The exact skip to gate behind env var
  - `calculate_scores.r`: The Docker command to replicate for auto-generation
  - `run_python_scores.py`: What to call to generate py scores

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: No skip with OHI_AUTO_GENERATE_FIXTURES=1
    Tool: Bash
    Preconditions: R and Py fixtures may or may not exist
    Steps:
      1. Run: OHI_AUTO_GENERATE_FIXTURES=1 uv run pytest tests/test_r_parity.py -v 2>&1 | tee /tmp/r-parity-output.txt
      2. Grep output for "1 passed"
      3. Grep output for "0 skipped"
    Expected Result: 1 passed, 0 skipped
    Evidence: .sisyphus/evidence/task-5-auto-gen.txt

  Scenario: Graceful skip without env var (no fixtures)
    Tool: Bash
    Preconditions: comparative/scores_2024_r.csv deleted
    Steps:
      1. mv comparative/scores_2024_r.csv /tmp/
      2. Run: uv run pytest tests/test_r_parity.py -v 2>&1 | tee /tmp/r-parity-skip.txt
      3. Grep for "1 skipped"
      4. mv /tmp/scores_2024_r.csv comparative/
    Expected Result: 1 skipped, exit code 0
    Evidence: .sisyphus/evidence/task-5-graceful-skip.txt

  Scenario: Auto-generates both R and Py fixtures when env var set
    Tool: Bash
    Preconditions: Both comparative/scores_2024_r.csv and scores_2024_py.csv deleted
    Steps:
      1. mv comparative/scores_2024_r.csv /tmp/
      2. mv comparative/scores_2024_py.csv /tmp/
      3. Run: OHI_AUTO_GENERATE_FIXTURES=1 uv run pytest tests/test_r_parity.py -v 2>&1 | tee /tmp/r-parity-autogen.txt
      4. Check: test -f comparative/scores_2024_r.csv && echo "R OK"
      5. Check: test -f comparative/scores_2024_py.csv && echo "Py OK"
      6. mv /tmp/scores_2024_r.csv comparative/ 2>/dev/null; mv /tmp/scores_2024_py.csv comparative/ 2>/dev/null
    Expected Result: Both files generated, test passes
    Evidence: .sisyphus/evidence/task-5-both-autogen.txt
  ```

  **Commit**: YES
  - Message: `test(parity): remove skip from test_r_parity.py, add env-var auto-generation`
  - Files: `tests/test_r_parity.py` (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `uv run ruff check src/ tests/` + `uv run mypy src/`. Review all changed files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Lint [PASS/FAIL] | Types [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real End-to-End QA** — `deep`
  Start from clean state (remove comparative/cache/ and comparative/fixtures/). Run `./run_all_tests.sh`. Verify: exit code 0, 44 parity tests pass, 0 skipped, all unit tests pass, baseline parity passes. Run again — verify idempotency (exit 0, no errors). Save full output to `.sisyphus/evidence/final-qa/`.
  Output: `Parity [44/44 pass] | Unit [N/N pass] | Skipped [0] | Idempotent [YES/NO] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Verify no new test files created. Verify no changes to src/ohipy/. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Scope Creep [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **1**: `test(parity): harden r_runner.py with UID/GID and error handling` — tests/parity/r_runner.py
- **2**: `test(parity): add lockfile and idempotency to setup_fixtures.py` — tests/parity/setup_fixtures.py
- **3**: `test: add run_all_tests.sh for fully automated test pipeline` — run_all_tests.sh
- **4**: `test(parity): remove skips from test_parity_full.py, add env-var auto-generation` — tests/test_parity_full.py
- **5**: `test(parity): remove skip from test_r_parity.py, add env-var auto-generation` — tests/test_r_parity.py

---

## Success Criteria

### Verification Commands
```bash
# Full pipeline from clean state
rm -rf comparative/cache/ comparative/fixtures/
./run_all_tests.sh
# Expected: exit 0

# Verify 44 parity tests pass
uv run pytest tests/test_parity_full.py -v 2>&1 | grep -E "44 passed|0 skipped"
# Expected: "44 passed, 0 skipped"

# Verify baseline parity passes
uv run pytest tests/test_r_parity.py -v 2>&1 | grep -E "1 passed|0 skipped"
# Expected: "1 passed, 0 skipped"

# Idempotency: second run
./run_all_tests.sh
# Expected: exit 0, fixtures reused

# Normal pytest still works (no Docker needed for unit tests)
uv run pytest tests/ --ignore=tests/test_parity_full.py --ignore=tests/test_r_parity.py -v
# Expected: all unit tests pass
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass with 0 skips
- [ ] Script is idempotent
- [ ] Normal pytest workflow preserved
