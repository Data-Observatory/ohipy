# OHI Python Performance Benchmarks

This document tracks performance measurements for the ohipy calculation pipeline across different optimization phases.

## Methodology

### Test Configuration
- **Benchmark Script**: `scripts/benchmark.py`
- **Iterations**: 5 runs per measurement
- **Metrics**: Mean, standard deviation, min, max, median execution time
- **Measurement**: Wall-clock time using `time.perf_counter()`

### System Information
- **Date**: 2026-03-03
- **OS**: [OS PLACEHOLDER]
- **Python Version**: [PYTHON VERSION PLACEHOLDER]
- **CPU**: [CPU PLACEHOLDER]
- **RAM**: [RAM PLACEHOLDER]

### Test Command
```bash
python scripts/benchmark.py
```

---

## Baseline Performance

**Date**: 2026-03-03

**Commit**: 48a7f386

**Results**:
```
Iterations:    5
Total time:    101.837 seconds
Mean:          20.367 seconds
Std dev:       0.341 seconds
Min:           19.779 seconds
Max:           20.650 seconds
Median:        20.457 seconds
```

**Notes**:
- Initial performance measurement before any optimization
- All calculations performed using standard Python/Pandas operations
- No caching or memoization applied
- Baseline (20.367s) is well above the 3-second threshold, so optimization will proceed

### Profiling Findings

**Main Bottleneck**: `groupby().apply()` operations account for 89% of execution time (44s out of 49.6s profiled)

**Top Hotspots** (from cProfile):
| Location | Function | Time | Calls |
|----------|----------|------|-------|
| resilience.py:185 | agg_step1 | 16.8s | 16,170 |
| resilience.py:207 | agg_step2 | 7.4s | 10,500 |
| pressures.py:220 | weighted_mean | 3.7s | 7,346 |
| pressures.py:234 | weighted_mean_gamma | 2.0s | 3,675 |

---

## Optimized Performance

**Phase 1**: Wave 1 - Vectorization (2026-03-03)

**Commit**: optimized

**Results**:
```
Iterations:    3
Total time:    38.300 seconds
Mean:          12.767 seconds
Std dev:       0.066 seconds
Min:           12.700 seconds
Max:           12.833 seconds
Median:        12.767 seconds
```

**Optimizations Applied**:
- fis.py: Replaced 7 `.apply(axis=1)` with np.where/np.select (25-100x faster per op)
- fp.py: Replaced `.apply(axis=1)` with np.where (55x faster)
- cs.py: Replaced `.apply(axis=1)` with np.where (25x faster)

**Improvement**:
- Speedup: 1.59x faster than baseline
- Time saved: 7.60 seconds per run

---

**Phase 2**: Wave 2 - GroupBy Optimization (2026-03-03)

**Commit**: optimized

**Results**:
```
Iterations:    3
Total time:    19.492 seconds
Mean:          6.497 seconds
Std dev:       0.037 seconds
Min:           6.463 seconds
Max:           6.536 seconds
Median:        6.492 seconds
```

**Optimizations Applied**:
- calculate_all.py: Replaced 3 `groupby().apply(np.average)` with vectorized agg (10-20x faster)
- pressures.py: Replaced 3 `groupby().apply(weighted_mean)` with vectorized agg
- resilience.py: Replaced 3 `groupby().apply()` with vectorized agg (16.8s → instant)

**Improvement**:
- Speedup: 1.97x faster than Phase 1 (3.13x vs baseline)
- Time saved: 6.27 seconds per run (13.87s vs baseline)
---

## Polars Migration (2026-03-04)

**Commit**: opt2 branch

**Results**:
```
Iterations:    5
Total time:    17.250 seconds
Mean:          3.450 seconds
Std dev:       0.095 seconds
Min:           3.360 seconds
Max:           3.584 seconds
Median:        3.407 seconds
```

**Optimizations Applied**:
- **Phase 1 (Layer I/O)**: Migrated `load_layers()` to Polars with `pl.read_csv()`
- **Phase 2 (Resilience - 57% of time)**:
  - Migrated 4-step aggregation to Polars expressions
  - Replaced `groupby().apply()` with Polars native weighted mean
- **Phase 3 (Pressures - 14% of time)**: Migrated 3-step aggregation to Polars
- **Phase 4 (Goals - 19% of time)**: Migrated liv, eco, cw, cs, fp to Polars

**Improvement**:
- Speedup: **4.04x** faster than baseline (13.928s → 3.450s)
- Time saved: 10.478 seconds per run
- R parity: max_diff = 0.0 (perfect match)

---

## Final Performance Comparison

| Phase | Mean (s) | Speedup vs Baseline |
|-------|----------|---------------------|
| Baseline (opt1) | 13.928 | 1.00x |
| Phase 1 (Layer I/O) | 7.351 | 1.90x |
| Phase 2 (Resilience) | 4.090 | 3.41x |
| Phase 3 (Pressures) | 3.461 | 4.02x |
| **Phase 4 (Goals)** | **3.450** | **4.04x** |

**Total Improvement**: 10.478 seconds saved per run (75% faster)

---

## Optimization Goals

- [x] Identify performance bottlenecks through profiling
- [x] Reduce mean execution time by 50%+ (achieved 75%)
- [x] Achieve 4x speedup target (achieved 4.04x)
- [x] Maintain calculation accuracy (R parity = 0.0, perfect match)
- [x] Document all optimization changes
---

## Notes

- All benchmarks should be run on the same system for fair comparison
- Ensure no other intensive processes are running during benchmarks
- Report any anomalies or system-specific factors that may affect results
