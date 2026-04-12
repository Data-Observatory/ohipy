# CHECKPOINT: parity-tests plan — 2026-04-09

## Status: ALL 10 Implementation Tasks COMPLETE. Final Verification Wave (F1-F4) REMAINING.

**Plan file**: `.sisyphus/plans/parity-tests.md`
**Branch**: main (not yet committed — changes are working tree only)

---

## What Was Done (Tasks 1-10)

### Wave 1 — Foundation (COMPLETE)
1. ✅ **Comparison Helper** — `tests/helpers/comparison.py` (318 lines)
   - `compare_scores()`: outer join, symmetric NaN, key uniqueness, categorized failures
   - `format_failure_report()`: dimension-first grouping, top-10 offenders
   - `assert_parity()`: raises AssertionError with formatted report
   
2. ✅ **pytest Markers + Hard-Fail Fixture** — `tests/conftest.py`, `pyproject.toml`
   - 3 markers: `integrity`, `parity`, `parity_full`
   - `strict_layers` fixture: hard-fails on missing declared layers

3. ✅ **Layer Audit Gate** — `tests/test_layer_audit.py` (203 lines)
   - 5 tests: exists, loadable, nonempty, has_data, no_duplicates
   - All marked `@pytest.mark.integrity`

### Wave 2 — Migration (COMPLETE)
4. ✅ **Migrate test_r_parity.py** — TOLERANCE 0.05→0.01, uses shared comparison, `@pytest.mark.parity`
5. ✅ **Migrate test_parity_full.py** — TOLERANCE 0.05→0.01, `_compare_scores()` deleted, uses shared comparison, `@pytest.mark.parity_full`
6. ✅ **Update compare_scores.py** — pandas→polars, tolerance 0.01, uses shared comparison
7. ✅ **Comparison Helper Unit Tests** — `tests/test_comparison_helper.py` (228 lines), 10 tests, all `@pytest.mark.integrity`

### Wave 3 — Coverage + Docs (COMPLETE)
8. ✅ **Edge Case Tests** — `tests/test_edge_cases.py` (220 lines), 7 tests, all `@pytest.mark.integrity`
   - Key finding: trend dimension uses [-1,1] range, not [0,100]; row counts differ between R (9477) and Py (10766)
9. ✅ **Test Runner Script** — `tests/run_all_tests.sh` — tier support with `--tier`, `--all`, timing per tier
10. ✅ **tests/AGENTS.md** — Updated with all new files, tiers, constraints

### Verification Status
- **27/27 non-Docker tests pass** (10 comparison helper + 5 layer audit + 7 edge cases + 5 existing)
- **44 parametrized parity tests collect correctly** (test_parity_full.py)
- **Ruff clean** on all new/modified test files
- **No changes to src/ohipy/** (scope guardrail upheld)
- **scores_2024_r.csv untouched** (immutable R reference)

---

## What Remains: Final Verification Wave (F1-F4)

4 parallel review agents need to run and ALL must APPROVE:

- [ ] **F1. Plan Compliance Audit** — `oracle` — Verify all "Must Have" implemented, all "Must NOT Have" absent
- [ ] **F2. Code Quality Review** — `unspecified-high` — Ruff, mypy, AI slop check on all changed files
- [ ] **F3. Real Manual QA** — `unspecified-high` — Execute all QA scenarios from every task
- [ ] **F4. Scope Fidelity Check** — `deep` — Verify 1:1 spec-to-implementation, no scope creep

After all 4 APPROVE → mark F1-F4 checkboxes in plan → present consolidated results to user → DONE.

---

## Files Changed (Uncommitted)

### New Files
- `tests/helpers/__init__.py` (1 line)
- `tests/helpers/comparison.py` (318 lines)
- `tests/test_layer_audit.py` (203 lines)
- `tests/test_comparison_helper.py` (228 lines)
- `tests/test_edge_cases.py` (220 lines)

### Modified Files
- `pyproject.toml` (+7 — pytest markers)
- `tests/conftest.py` (+37 — markers + strict_layers fixture)
- `tests/test_r_parity.py` (+12, -46 — migrated to shared comparison)
- `tests/test_parity_full.py` (+7, -39 — migrated, _compare_scores deleted)
- `tests/comparative/compare_scores.py` (+32, -50 — pandas→polars, 0.01 tolerance)
- `tests/comparative/scores_2024_py.csv` (regenerated — 85 changed rows)
- `tests/run_all_tests.sh` (+104, -21 — tier support)
- `tests/AGENTS.md` (+66, -10 — documentation)

### NOT Changed (verified)
- `src/ohipy/` — ZERO changes (scope guardrail)
- `tests/comparative/scores_2024_r.csv` — untouched (immutable)
- `data/` — untouched

---

## How to Resume (for future Atlas session)

1. **Read this file**: `.sisyphus/plans/parity-tests-checkpoint.md`
2. **Read the plan**: `.sisyphus/plans/parity-tests.md` — check remaining `- [ ]` items
3. **Run sanity check**: `uv run pytest tests/test_layer_audit.py tests/test_comparison_helper.py tests/test_edge_cases.py tests/test_overrides.py tests/test_runner_basic.py -v` → expect 27 passed
4. **Start Final Wave**: Launch F1-F4 in parallel using `task()` with appropriate agents
5. **After all APPROVE**: Mark F1-F4 in plan, present to user, commit

### Agent Dispatch for Final Wave
```
F1: task(subagent_type="oracle", load_skills=[], run_in_background=false, prompt="Plan compliance audit...")
F2: task(category="unspecified-high", load_skills=[], run_in_background=false, prompt="Code quality review...")
F3: task(category="unspecified-high", load_skills=[], run_in_background=false, prompt="Manual QA...")
F4: task(category="deep", load_skills=[], run_in_background=false, prompt="Scope fidelity check...")
```

### Key Context for Resumption
- Plan name: `parity-tests`
- Plan file: `.sisyphus/plans/parity-tests.md`
- Notepad: `.sisyphus/notepads/parity-tests/` (minimal — most work was tracked in plan)
- All code is uncommitted — changes are in working tree only
- No Docker needed for what remains (F1-F4 are read-only reviews)
- The comparison helper is the lynchpin — `tests/helpers/comparison.py` — everything depends on it

---

## Commit Strategy (3 atomic commits recommended)
1. Wave 1: `test(parity): add shared comparison helper, markers, and layer audit gate`
2. Wave 2: `test(parity): migrate parity tests to 0.01 tolerance with outer-join comparison`
3. Wave 3: `test(parity): add edge case tests, tiered runner, and update AGENTS.md`
