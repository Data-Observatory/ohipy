# OHIpy Benchmark Suite

This directory contains benchmarking tools for measuring the performance of the Ocean Health Index (OHI) calculations across different branches and optimization stages.

## Two Benchmark Tools
| Tool | Purpose | When to Use |
|------|---------|-------|
| **ASV Benchmark** (`time_run_python_scores.py`) | Longitudinal performance tracking, historical regression detection, Continuous monitoring | Ad-hoc branch comparisons, One-time checks |
| **Cross-Branch Harness** (`benchmark_branches.py`) | Quick branch-to-branch timing | Isolated worktrees | Before/after optimization work | CI checks |
## Quick Start
### Verify ASV Setup
```bash
uv run python -m asv check
```

### Run ASV Benchmark (Current Code)
```bash
# Run benchmark on current code
uv run python -m asv run --quick -b time_run_python_scores

# Compare two branches
uv run python -m asv asv continuous main opt1
```

### Run Cross-Branch Harness
```bash
# Quick check - single branch
uv run python benchmarks/benchmark_branches.py --branches opt2 --warmups 0 --iterations 1

# Full comparison - all three branches
uv run python benchmarks/benchmark_branches.py --branches main opt1 opt2 --warmups 1 --iterations 3
```

## ASV Dashboard
```bash
# Generate HTML dashboard
uv run python -m asv publish

# View locally at uv run python -m asv preview
```

## Real Branch Timings (Measured 2026-03-10)
| Branch | Commit | Mean (s) | Std (s) | Min (s) | Max (s) | Median (s) | Relative to opt2 |
|-------|---------|-------|----------|-------|
| opt2 | ff1f848 | 6.388 | 0.036 | 6.366 | 6.430 | 6.368 | 1.00x (fastest) |
| opt1 | c2322b6 | 9.789 | 0.211 | 9.616 | 10.024 | 9.727 | 1.53x slower |
| main | 39ecc73 | 19.632 | 0.098 | 19.526 | 19.720 | 19.650 | 3.07x slower |
**Key Findings:**
- `opt2` (Polars) is **~3.07x faster** than `main` (baseline)
- `opt1` is **~1.53x faster** than `opt2` (vectorization)
- `main` is **~3.07x slower** than `opt2`
## Files
| File | Purpose |
|------|---------|
| `__init__.py` | Makes this a Python package discover| `time_run_python_scores.py` | ASV benchmark that `benchmark_branches.py` | Cross-branch timing harness |

## ASV Configuration (`asv.conf.json`)
```json
{
  "version": 1,
  "project": "ohipy",
  "project_url": "https://github.com/Data-Observatory/ohipy",
  "repo": ".",
  "branches": ["main", "opt1", "opt2"],
  "benchmark_dir": "benchmarks",
  "results_dir": ".asv/results",
  "html_dir": ".asv/html",
  "environment_type": "virtualenv",
  "install_command": [
    "in-dir={build_dir} python -m pip install . --force-reinstall",
  ],
  "pythons": ["3.14"],
  "matrix": {}
}
```

## Important Notes
### ASV Invocation
On Windows PowerShell, `uv run asv` may fail.use Use:
```bash
uv run python -m asv check
uv run python -m asv run --quick
uv run python -m asv continuous main opt2
```

### chl/ Directory (for R comparison only)

The `chl/` directory is not tracked in git and is only needed for R validation. The benchmark script automatically handles data requirements:
- **For new branches with `data/` directory (opt2)**: Uses included `data/` files
- **For old branches without `data/` (main, opt1)**: Symlinks/copies `chl/` as needed

The script will create/copy the data as needed in isolated worktrees.

### Performance Tips
- Run ASV on a clean worktree first (first time takes longer for cold caches)
- For accurate timing, run multiple iterations (3+) and average results
- Run `asv check` before benchmarking to catch issues early
- If comparing branches, always test on a clean worktree first

## Troubleshooting
| Problem | Solution |
|---------|----------|
| `FileNotFoundError: chl/` | The `chl/` directory is not tracked in git. The benchmark script symlinks/copies it as needed |
| `ModuleNotFoundError` | Run `uv sync` and ensure `polars`/`pyarrow` is installed |
| `uv run` fails | On Windows PowerShell, use `uv run python -m asv ...` instead |
| ASV check fails | Ensure `asv.conf.json` exists and `pyproject.toml` has dev dependencies |

## Cross-Branch Harness Details
The harness creates isolated git worktrees for each branch and timing `scripts/run_python_scores.py` and measuring the full pipeline execution time.

**Output**: Console table + JSON file (`comparative/branch_benchmark_*.json`)

**Features:**
- Clean isolation via git worktrees
- Warmup runs to configurable iterations
- Statistical analysis (mean, std, min, max, median)
- Speedup comparisons
- JSON output for reproducibility

## Related Files
| File | Purpose |
|------|---------|
| `../benchmarks.md` | Root-level benchmark documentation |
| `../asv.conf.json` | ASV configuration |
| `../comparative/` | Benchmark JSON outputs |
