# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-08
**Commit:** e865c35
**Branch:** main

## OVERVIEW

Ocean Health Index (OHI) Python calculation library. Port of R ohicore for regional ocean health scoring. Pure polars implementation matching R output exactly.

## STRUCTURE

```
ohipy/
├── src/ohipy/              # Main package (src layout)
│   ├── goals/              # 18 goal calculation functions [AGENTS.md]
│   ├── dimensions/         # Pressures & resilience calculators
│   ├── config/             # YAML/CSV config loading
│   ├── layers/             # Data layer loading (polars-native)
│   ├── calculate/          # Trend & goal index math
│   ├── calculate_all.py    # Main orchestrator (434 lines, 11-step workflow)
│   ├── types.py            # GoalResult, ConfigData types
│   ├── runner.py           # OHIRunner class
│   ├── cache.py            # LayerCache class
│   ├── config_overlay.py   # ConfigOverlay for weight/disable overrides
│   ├── postprocess.py      # Score finalization
│   └── statistics.py       # Statistical calculations
├── data/                   # Config + layer data (included in repo)
│   ├── conf/               # 6 CSVs: goals, pressures/resilience matrices & categories
│   ├── layers/{csv,parquet}/ # 227 layer data files each
│   └── layers.csv          # Layer metadata (99 rows)
├── scripts/                # CLI entry points
├── tests/                  # Test suite [AGENTS.md]
├── benchmarks/             # Performance benchmarking
├── js/                     # Browser-based calculator prototype
└── chl/                    # Cloned R reference repo (gitignored)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new goal | `src/ohipy/goals/{goal}.py` | Copy pattern from `fis.py` |
| Modify pressure calc | `src/ohipy/dimensions/pressures.py` | 426 lines, gamma-weighted matrix ops |
| Modify resilience calc | `src/ohipy/dimensions/resilience.py` | 449 lines, mirrors pressures |
| Main orchestrator | `src/ohipy/calculate_all.py` | 434 lines, 11-step workflow |
| Load config/layers | `src/ohipy/config/`, `src/ohipy/layers/` | YAML + CSV via polars |
| Trend/index math | `src/ohipy/calculate/__init__.py` | Vectorized OLS, goal index formula |
| Type definitions | `src/ohipy/types.py` | GoalResult, ConfigData |
| Config overrides | `src/ohipy/config_overlay.py` | Weight/disable goal modifications |
| Validate vs R | `tests/comparative/compare_scores.py` | Single source of truth |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `calculate_all` | func | `calculate_all.py:81` | Main orchestrator, sole public API |
| `calculate_pressures_all` | func | `pressures.py:33` | Pressure dimension calculator |
| `calculate_resilience_all` | func | `resilience.py:25` | Resilience dimension calculator |
| `load_config` | func | `config/__init__.py:10` | YAML + 6 CSVs → config dict |
| `load_layers` | func | `layers/__init__.py:8` | Parquet/CSV → layers dict |
| `select_layers_data` | func | `layers/__init__.py:82` | Filter layers by goal/target |
| `calculate_trend` | func | `calculate/__init__.py:7` | Vectorized OLS trend |
| `calculate_goal_index` | func | `calculate/__init__.py:114` | xF = (1+β·trend+(1-β)(r-p))·status/2 |

## CONVENTIONS

- **Python 3.13+**, hatchling build, src layout
- **Strict typing** - `disallow_untyped_defs=true` in mypy
- **Ruff** - line-length=100, select=[E,F,I,N,W,UP]
- **Pyright suppressions** accepted in orchestration files: `calculate_all.py`, `runner.py`, `pressures.py`
- **R parity** - Comments reference R source lines (e.g., "R functions.R lines 17-180")
- **Scores schema** - All scores: `pl.DataFrame` with `[region_id, goal, dimension, score]`
- **Dimensions** - status, trend, pressures, resilience, future, score, Index
- **Score scale** - 0-100 external, 0-1 internal

## ANTI-PATTERNS (THIS PROJECT)

- **DO NOT** change calculation order - must match R exactly
- **DO NOT** use different rounding - pressures/resilience `.round(2)`, status/trend `.round(4)`
- **DO NOT** skip weighted.mean na.rm=TRUE behavior - NaN handling is critical
- **DO NOT** modify `tests/comparative/scores_2024_r.csv` - immutable fixture
- **DO NOT** fix cw.py R bug replication (lines 211-233) without team approval

## UNIQUE STYLES

- Goal functions: pre-index return `(status_df, trend_df)`, post-index return updated `scores_df`
- Post-index signatures vary: `LE(scores, layers)` vs `FP(layers, scores)`
- Config dict keys: `config`, `goals`, `pressures_matrix`, `resilience_matrix`, `pressure_categories`, `resilience_categories`, `layers`, `scenario_data_years`
- Layers dict keys: `data` (layer_name → polars DataFrame), `meta` (polars DataFrame)
- Goal codes: 2-3 letter uppercase: FIS, MAR, FP, AO, NP, CS, CP, TR, LIV, ECO, LE, ICO, LSP, SP, CW, HAB, SPP, BD
- Resilience capped: `r = min(r, p)` where p is pressure
- Global scores: area-weighted mean (region_id=0)

## COMMANDS

```bash
uv sync                                          # Install deps
uv run python scripts/run_python_scores.py        # Run calculation
uv run python tests/comparative/compare_scores.py # Validate vs R
uv run ruff check src/                            # Lint
uv run mypy src/                                  # Type check
uv run pytest tests/                              # Run tests
./tests/run_all_tests.sh                          # Full suite (Docker + fixtures)
./tests/run_all_tests.sh --skip-docker --no-fixtures  # Smoke test
docker run --rm -v "$PWD":/home/project -w /home/project ohicore-r-env Rscript tests/comparative/calculate_scores.r  # Generate R scores
```

## NOTES

- `data/` included in repo with all config and layer files
- `chl/` cloned separately only for R comparison (`git clone https://github.com/OHI-Science/chl`)
- R validation requires Docker (rocker/r-ver:4.2.3, dplyr <= 1.0.10 pinned)
- 44 parity tests: 4 datasets (original + 3 noise levels) × 11 variations
- Layer loading: parquet preferred, CSV fallback, uses polars throughout
- No CI/CD yet (TODO in README)
- `js/` contains browser-based calculator prototype (not part of Python package)
