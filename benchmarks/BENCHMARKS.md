# OHIpy Performance Benchmarks

Performance measurements for the ohipy calculation pipeline across optimization stages.

## Quick Results (2026-03-11)

| Branch | Implementation | Real (s) | User (s) | Speedup (user) |
|--------|---------------|----------|----------|----------------|
| **opt0** | Pandas (legacy) | 30.2 | 20.0 | 1.00x |
| **opt1** | Vectorized | 21.5 | 11.0 | **1.82x** |
| **opt2** | Polars | 21.7 | 7.8 | **2.56x** |

**Command measured**: `time uv run python scripts/run_python_scores.py`

> **Note**: `real` = wall clock time (includes I/O), `user` = CPU computation time

---

## Branch Descriptions

| Branch | Purpose | Key Changes |
|--------|---------|-------------|
| `opt0` | Legacy/original | Pure Pandas implementation, no optimizations |
| `opt1` | Vectorization | Replaced `.apply()` with `np.where`/`np.select`, vectorized aggregations |
| `opt2` | Polars | Migrated I/O, pressures, resilience, and goals to Polars |

---

## Understanding Time Metrics

When running `time uv run python scripts/run_python_scores.py`:

| Metric | What it Measures | Typical Value |
|--------|-----------------|---------------|
| **real** | Wall clock time (end-to-end) | 21-30s |
| **user** | CPU time in user mode (computation) | 7-20s |
| **sys** | CPU time in kernel mode (I/O syscalls) | 1-3s |

**For optimization comparison, use `user` time** - it isolates the computation from I/O overhead.

### Time Breakdown

- **I/O overhead** (CSV reading, Python startup): ~10-14s (constant)
- **Computation** (varies by branch):
  - opt0: ~20s
  - opt1: ~11s
  - opt2: ~7.8s

---

## Optimization History

### Phase 1: Vectorization (opt1)

**Changes**:
- Replaced `df.apply(axis=1)` with `np.where`/`np.select` (25-100x faster per operation)
- Vectorized `groupby().apply(np.average)` with native aggregations
- Affected files: `fis.py`, `fp.py`, `cs.py`, `calculate_all.py`, `pressures.py`, `resilience.py`

**Result**: 20s → 11s user time (**1.82x faster**)

### Phase 2: Polars Migration (opt2)

**Changes**:
- **Layer I/O**: Migrated `load_layers()` to `pl.read_csv()`
- **Resilience** (57% of compute time): 4-step aggregation with Polars expressions
- **Pressures** (14% of compute time): 3-step aggregation with Polars
- **Goals** (19% of compute time): Migrated liv, eco, cw, cs, fp to Polars

**Result**: 11s → 7.8s user time (**1.41x faster than opt1**, **2.56x faster than opt0**)

---

## Benchmark Tools

### Cross-Branch Harness

```bash
# Quick comparison
uv run python benchmarks/benchmark_branches.py --branches opt0 opt1 opt2 --warmups 0 --iterations 1

# Full comparison with statistics
uv run python benchmarks/benchmark_branches.py --branches opt0 opt1 opt2 --warmups 1 --iterations 3
```

### ASV (Airspeed Velocity)

For longitudinal tracking and regression detection:

```bash
# Verify setup
uv run python -m asv check

# Run benchmark
uv run python -m asv run --quick -b time_run_python_scores

# Compare branches
uv run python -m asv continuous opt0 opt2

# Generate HTML dashboard
uv run python -m asv publish
uv run python -m asv preview
```

---

## Running Benchmarks

```bash
# Setup
git clone https://github.com/Data-Observatory/ohipy
cd ohipy
git clone https://github.com/OHI-Science/chl
uv sync --extra dev

# Run on current branch (with detailed timing)
time uv run python scripts/run_python_scores.py

# Compare all branches
uv run python benchmarks/benchmark_branches.py --branches opt0 opt1 opt2
```

---

## Notes

- All benchmarks run on the same system for fair comparison
- Ensure no other intensive processes during benchmarks
- R parity validation: `uv run python tests/comparative/compare_scores.py`
- `user` time is the best metric for comparing optimization effectiveness
