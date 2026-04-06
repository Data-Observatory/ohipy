# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-12
**Commit:** 8707f5a
**Branch:** opt2

## OVERVIEW

Ocean Health Index (OHI) Python calculation library. Port of R ohicore for regional ocean health scoring. Pure pandas/numpy + polars implementation matching R output exactly.

## STRUCTURE

```
ohipy/
├── src/ohipy/           # Main package (src layout)
│   ├── goals/           # 18 goal calculation functions
│   ├── dimensions/      # Pressures & resilience calculators
│   ├── config/          # YAML/CSV config loading
│   ├── layers/          # Data layer loading
│   └── calculate/       # Trend & goal index math
├── data/                # Configuration and layer data (included in repo)
│   ├── conf/            # goals.csv and other config files
│   ├── layers/          # Layer data files
│   └── layers.csv       # Layer metadata
├── tests/comparative/         # R validation (Docker, comparison scripts)
└── chl/                 # Cloned R reference repo (gitignored, for R comparison only)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new goal | `src/ohipy/goals/{goal}.py` | Copy pattern from `fis.py` |
| Modify pressure calc | `src/ohipy/dimensions/pressures.py` | 403 lines, complex matrix ops |
| Modify resilience calc | `src/ohipy/dimensions/resilience.py` | 407 lines, mirrors pressures |
| Main orchestrator | `src/ohipy/calculate_all.py` | 377 lines, 11-step workflow |
| Load config/layers | `src/ohipy/config/`, `src/ohipy/layers/` | YAML + CSV parsing |
| Trend/index math | `src/ohipy/calculate/__init__.py` | Linear regression, goal index formula |
| Validate vs R | `tests/comparative/compare_scores.py` | Single source of truth |

## CONVENTIONS

- **Python 3.13+** - Uses modern type hints, no backwards compat
- **Strict typing** - `disallow_untyped_defs=true` in mypy
- **Line length** - 100 chars (ruff enforced)
- **Imports** - Sorted by ruff (I rule)
- **Pandas-heavy** - `# pyright: reportGeneralTypeIssues=false` accepted in orchestration files
- **R parity** - Comments reference R source lines (e.g., "R CalculateAll.R lines 193-201")

## ANTI-PATTERNS (THIS PROJECT)

- **DO NOT** change calculation order - must match R exactly
- **DO NOT** use different rounding - R uses 2 decimal places
- **DO NOT** skip weighted.mean na.rm=TRUE behavior - NaN handling is critical
- **DO NOT** modify `tests/comparative/scores_2024_r.csv` - this is the fixture

## UNIQUE STYLES

- Goal functions return `(status_df, trend_df)` tuple
- Config is a dict with keys: `config`, `goals`, `pressures_matrix`, `resilience_matrix`, etc.
- Layers is a dict with keys: `data` (layer_name → DataFrame), `meta` (DataFrame)
- All scores DataFrame has columns: `[region_id, goal, dimension, score]`
- Goal codes are 2-3 letter uppercase: FIS, MAR, FP, AO, NP, CS, CP, TR, LIV, ECO, LE, ICO, LSP, SP, CW, HAB, SPP, BD

## COMMANDS

```bash
# Install deps (requires uv)
uv sync

# Run calculation
uv run python scripts/run_python_scores.py

# Validate against R
uv run python tests/comparative/compare_scores.py

# Lint
uv run ruff check src/

# Type check
uv run mypy src/

# Run tests
uv run pytest tests/

# Generate R scores (requires Docker)
docker run --rm -v "$PWD":/home/project -w /home/project ohicore-r-env Rscript tests/comparative/calculate_scores.r
```

## NOTES

- `data/` directory is included in the repo and contains all configuration and layer files
- `chl/` repo must be cloned separately only for R comparison (`git clone https://github.com/OHI-Science/chl`)
- R validation requires Docker (dplyr <= 1.0.10 pinned)
- Tests in `tests/` use pytest; main validation is `tests/comparative/compare_scores.py`
- Global scores use area-weighted mean (region_id=0)
- Resilience is capped: `r = min(r, p)` where p is pressure
- No CI/CD yet (TODO in README)
- Layer loading uses polars for performance, converts to pandas
