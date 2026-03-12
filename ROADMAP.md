# OHIpy Roadmap

**Generated:** 2026-03-12
**Context:** Post-parquet-support implementation analysis

---

## 1. Pending Features

Features to implement next, ordered by priority and effort.

### 1.1 Profiling Harness (Highest Priority)

**Why:** Before optimizing, we need concrete timing data.

**What:**
- Add `scripts/profile_run.py` to collect cProfile output
- Profile both `load_layers()` and `calculate_all()` separately
- Output top N functions by cumulative time

**Effort:** Low (<1 hour)

**Implementation:**
```python
# scripts/profile_run.py
import cProfile
import pstats
from ohipy.config import load_config
from ohipy.layers import load_layers
from ohipy.calculate_all import calculate_all

config = load_config()
layers = load_layers(config)

with cProfile.Profile() as pr:
    calculate_all(config, layers)

pstats.Stats(pr).sort_stats("cumulative").print_stats(30)
```

---

### 1.2 Layer Cache Integration

**Why:** `LayerCache` class exists but is unused. Repeated runs reload all 227 layers.

**What:**
- Integrate `LayerCache` into `load_layers()` or `OHIRunner`
- Cache by `(layer_name, scenario_year)` key
- Invalidate on config changes

**Effort:** Low (1-2 hours)

**Location:** `src/ohipy/cache.py` (already exists), `src/ohipy/layers/__init__.py`

---

### 1.3 Config/CLI Validation

**Why:** `layer_format` accepts any string; no validation.

**What:**
- Validate `layer_format` is `"csv"` or `"parquet"` in config loader
- Add clear error messages for invalid values
- Optional: log which format is actually used (preference vs fallback)

**Effort:** Low (<1 hour)

**Location:** `src/ohipy/config/__init__.py`

---

### 1.4 Format Selection at API Level

**Why:** Format preference is config + CLI only. No API control.

**What:**
- Add `format_preference` parameter to `load_layers(config, format_preference=None)`
- Add `format_preference` parameter to `OHIRunner.run()`
- Allow runtime override without modifying config

**Effort:** Low (1-2 hours)

**Location:** `src/ohipy/layers/__init__.py`, `src/ohipy/runner.py`

---

### 1.5 Consolidate Layers into Single Parquet (Future)

**Why:** 227 small files have overhead. Single parquet with partition column is faster.

**What:**
- Create `data/layers.parquet` with `layer_name` column
- Update `load_layers()` to read single file
- Keep individual files for backward compatibility

**Effort:** Medium (half day)

**Location:** `scripts/consolidate_layers.py`, `src/ohipy/layers/__init__.py`

---

## 2. Performance Optimization Roadmap

**Current:** ~4 seconds
**Target:** <1 second
**Feasibility:** Yes, achievable. Data is small (~1.5MB Parquet), bottleneck is Python overhead and conversions.

---

### Phase 1: Measure First (MUST DO)

**Goal:** Identify real bottlenecks with data, not guesses.

**Actions:**
1. Add profiling script (see 1.1 above)
2. Run profile on current implementation
3. Document top 10 functions by `cumtime`

**Expected Output:** Hard evidence of where time goes (IO vs computation vs conversion)

**Effort:** <1 hour

---

### Phase 2: Remove Conversion Overhead

**Why it matters:**
- Every layer converts Polars → Pandas immediately (227 conversions)
- Pressures/resilience bounce pandas ↔ polars multiple times
- Each `.to_pandas()` copies data from Arrow (Rust) to NumPy (C)

**Actions:**

1. **Keep layers as Polars internally**
   - Remove `.to_pandas()` from `load_layers()`
   - Store Polars DataFrames in `layers["data"]`
   - Convert to pandas only on demand

2. **Lazy conversion wrapper**
   ```python
   class LazyPandasDict:
       def __init__(self, polars_data: dict):
           self._pl = polars_data
           self._pd_cache = {}
       
       def __getitem__(self, key):
           if key not in self._pd_cache:
               self._pd_cache[key] = self._pl[key].to_pandas(
                   use_pyarrow_extension_array=True
               )
           return self._pd_cache[key]
   ```

3. **Zero-copy conversion**
   - Use `df.to_pandas(use_pyarrow_extension_array=True)`
   - Requires `pyarrow` installed, pandas ≥ 2.0
   - Points pandas at existing Arrow memory instead of copying

**Expected Gain:** ~1.0-1.5 seconds

**Effort:** Medium (2-3 hours)

**Files to modify:**
- `src/ohipy/layers/__init__.py`
- `src/ohipy/dimensions/pressures.py`
- `src/ohipy/dimensions/resilience.py`

---

### Phase 3: Vectorize Goal Index Loop

**Bottleneck identified:**
```python
# calculate_all.py lines 144-219
for goal in goals_with_status:
    for rid in valid_regions:
        # Individual goal index calculation
        status = goal_scores.loc[rid, "status"] / 100.0
        trend = goal_scores.loc[rid, "trend"]
        # ... 8-12 more lines per region
```

**Actions:**

Replace nested loop with vectorized pandas operations:

```python
# Pivot once
goal_scores = scores[scores["dimension"].isin(["status", "trend", "pressures", "resilience"])]
pivoted = goal_scores.pivot_table(
    index=["region_id", "goal"], 
    columns="dimension", 
    values="score"
)

# Vectorized calculations
pivoted["status_norm"] = pivoted["status"] / 100
pivoted["p_norm"] = pivoted.get("pressures", 0) / 100
pivoted["r_norm"] = pivoted.get("resilience", 0) / 100
pivoted["r_capped"] = pivoted[["r_norm", "p_norm"]].min(axis=1)
pivoted["r_p"] = pivoted["r_capped"] - pivoted["p_norm"]

# Vectorized xF and score
BETA = 0.67
pivoted["xF"] = (1 + BETA * pivoted["trend"] + (1 - BETA) * pivoted["r_p"]) * pivoted["status_norm"]
pivoted["xF"] = pivoted["xF"].clip(0, 1)
pivoted["score"] = (pivoted["status_norm"] + pivoted["xF"]) / 2
pivoted["score"] = pivoted["score"].clip(0, 1)
```

**Expected Gain:** ~0.3-0.7 seconds

**Effort:** Medium (2-3 hours)

**Files to modify:**
- `src/ohipy/calculate_all.py`

---

### Phase 4: Optimize Pressures/Resilience

**Bottleneck:**
- Multiple `pd.concat()` operations
- Multiple pandas ↔ polars round-trips
- Repeated merge operations

**Actions:**

1. **Stay in Polars end-to-end**
   - Remove intermediate `.to_pandas()` calls
   - Convert to pandas only at function return

2. **Consolidate concat operations**
   - Collect all DataFrames first
   - Single `pd.concat()` or `pl.concat()` at end

3. **Reduce merge overhead**
   - Pre-join commonly merged datasets
   - Use integer keys instead of strings where possible

**Expected Gain:** ~0.5-1.0 seconds

**Effort:** Medium (3-4 hours)

**Files to modify:**
- `src/ohipy/dimensions/pressures.py`
- `src/ohipy/dimensions/resilience.py`

---

### Phase 5: Parallelize Goal Calculations

**Why:** The 14 pre-index goals are independent—no shared state.

**Actions:**

```python
from concurrent.futures import ThreadPoolExecutor

def calculate_goals_parallel(goals_list, layers):
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(GOAL_FUNCTIONS[goal], layers)
            for goal in goals_list
        ]
        results = [f.result() for f in futures]
    return results
```

**Expected Gain:** 20-40% wall-time reduction

**Effort:** Medium (2-3 hours)

**Files to modify:**
- `src/ohipy/calculate_all.py`

**Watch out:**
- Verify scipy releases GIL (it generally does)
- If not, use `ProcessPoolExecutor` with pickle overhead

---

## 3. Projected Timeline After Optimization

| Component | Current (est.) | After | Technique |
|-----------|---------------|-------|-----------|
| Config loading | ~0.2s | ~0.1s | Parquet config matrices |
| Layer loading | ~1.5-2s | ~0.2s | Batch polars, lazy pandas, zero-copy |
| 14 goal functions | ~0.8s | ~0.5s | Stay in polars, parallelize |
| Pressures + Resilience | ~1s | ~0.3s | Eliminate round-trips, consolidate merges |
| Goal index calculation | ~0.5s | ~0.05s | Vectorize |
| Post-processing | ~0.1s | ~0.05s | Minimal gain |
| **Total** | **~4s** | **~0.5-0.8s** | |

---

## 4. Critical Constraints

### R Parity Must Be Preserved

After **each optimization**, run:
```bash
uv run python comparative/compare_scores.py
```

**Why:** Vectorized operations may produce slightly different floating-point results due to order of operations. Always verify against the R fixture.

### Watch Out For

1. **Polars lazy evaluation:** Don't call `.collect()` prematurely. Chain operations first.
2. **Thread parallelism:** Some scipy functions may not release GIL. Test empirically.
3. **Memory bloat:** Caching 227 layers in memory is fine for this data size, but monitor if data grows.

---

## 5. Implementation Order

Recommended sequence:

1. **Week 1:** Profiling script + LayerCache integration
2. **Week 2:** Remove conversion overhead (Phase 2)
3. **Week 3:** Vectorize goal index loop (Phase 3)
4. **Week 4:** Optimize pressures/resilience (Phase 4)
5. **Optional:** Parallelize goals (Phase 5) if not yet <1s

---

## 6. Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Execution time | <1s | `time uv run python scripts/run_python_scores.py` |
| R parity | max diff <0.05 | `uv run python comparative/compare_scores.py` |
| Memory usage | <500MB | Monitor during profiling |
| Code quality | No regressions | `uv run ruff check src/ && uv run mypy src/` |

---

## References

- Polars zero-copy: https://docs.pola.rs/py-polars/html/reference/dataframe/api/polars.DataFrame.to_pandas.html
- Polars lazy optimizations: https://docs.pola.rs/user-guide/lazy/optimizations/
- Pandas 2.0 Arrow backend: https://pandas.pydata.org/docs/whatsnew/v2.0.0.html
