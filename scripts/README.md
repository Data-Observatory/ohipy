# scripts/

Standalone utility scripts. Run from the repo root with `uv run python scripts/<name>.py`.

## run_python_scores.py

Run the OHI calculation pipeline and write scores to CSV or Parquet. Full CLI
reference and examples (multi-year runs, weight overrides, disabling layers,
custom data paths) are in the main [README.md](../README.md#running-the-pipeline).

```
uv run python scripts/run_python_scores.py --year 2024 --output scores.csv
```

## convert_layers_to_parquet.py

Converts every CSV in `data/layers/csv/` to Parquet in `data/layers/parquet/`,
verifying a round-trip (CSV -> Parquet -> read-back) matches for each file.
No arguments; paths are hardcoded module constants (`CSV_DIR`, `PARQUET_DIR`).
Re-run after adding or editing a layer CSV so the Parquet copy stays in sync.

```
uv run python scripts/convert_layers_to_parquet.py
```

## convert_ideos_layers.py

Converts parquet layers exported by proj-IDEOS-metas into chl/comunas
OHI-core CSV layers: selects the 2024 assessment data, renames columns to
OHI-core conventions, writes a parallel scenario under
`chl/comunas/layers_ideos/` without touching `chl/comunas/layers/`.

```
uv run python scripts/convert_ideos_layers.py [--parquet-dir DIR] [--out-dir DIR]
```

`--parquet-dir` / `--out-dir` override the default source/output locations
(see the script header for current defaults). Run with `--help` for details.

## profile_run.py

Profiles the full pipeline (`load_config` -> `load_layers` -> `calculate_all`)
with `cProfile`, prints the top 30 functions by cumulative time, and writes
the same report to `.sisyphus/evidence/task-1-profile-output.txt`. No
arguments, no options.

```
uv run python scripts/profile_run.py
```

## generate_layer_goal_map.py

Generates a long-format CSV mapping every input layer in `data/layers.csv`
to the goal(s)/subgoal(s) it drives, and its role (status/trend, pressure,
resilience, element weight, spatial support, or unused). One row per
(layer, goal, role) so the output filters/pivots directly. Sourced from
`data/layers.csv`, `data/conf/pressures_matrix.csv`,
`data/conf/resilience_matrix.csv`, `src/ohipy/config/config.yaml`, and a
short hardcoded list of goal/layer links that exist only in
`src/ohipy/goals/*.py` code (documented in the script header — re-verify
with the grep commands there if goal code changes).

```
uv run python scripts/generate_layer_goal_map.py -o layer_goal_map.csv
```

Defaults to stdout if `-o`/`--output` is omitted.
