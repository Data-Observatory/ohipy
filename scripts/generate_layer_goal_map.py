#!/usr/bin/env python3
"""Generate a long-format CSV mapping every input layer to the goal(s) it drives.

One row per (layer, goal, role) combination, so the output can be filtered/pivoted
directly (e.g. "all pressure layers for CW", "everything that feeds HAB").

Sources, in order of precedence:
  - data/layers.csv              -> targets column: direct status/trend layers
  - data/conf/pressures_matrix.csv   -> goal x pressure-layer matrix (cell = category weight 1-3)
  - data/conf/resilience_matrix.csv  -> goal x resilience-layer matrix (cell = "x")
  - src/ohipy/config/config.yaml -> element_mappings.{resilience,pressures}: generic
    per-goal element-weighting layers (targets == "weight" in layers.csv)
  - a short hardcoded list for goal/layer links that live only in Python code
    (grepped from src/ohipy/goals/*.py, not expressed in any csv/yaml config)

Usage:
    python scripts/generate_layer_goal_map.py [-o output.csv]
    Defaults to stdout.
"""

import argparse
import csv
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
LAYERS_CSV = REPO_ROOT / "data" / "layers.csv"
PRESSURES_MATRIX = REPO_ROOT / "data" / "conf" / "pressures_matrix.csv"
RESILIENCE_MATRIX = REPO_ROOT / "data" / "conf" / "resilience_matrix.csv"
GOALS_CSV = REPO_ROOT / "data" / "conf" / "goals.csv"
CONFIG_YAML = REPO_ROOT / "src" / "ohipy" / "config" / "config.yaml"

# Links that exist only in Python code (src/ohipy/goals/*.py), not in any
# csv/yaml config. Re-check with:
#   grep -rn "_require_polars_layer\|data_layers.get\|data_layers\[" src/ohipy/goals/*.py
CODE_ONLY_LINKS = [
    # goal, layer, role, detail
    ("CW", "cw_connutrientester", "pressure (code-level, not in matrix)", ""),
    ("CW", "cw_connutrientester_trend", "pressure trend (code-level, not in matrix)", ""),
    ("CW", "rgn_area", "spatial support (area weighting, src/ohipy/goals/cw.py)", ""),
]

# Layers present in data/layers.csv that no src/ohipy code path reads.
# Re-check with: grep -rn "<layer_name>" --include="*.py" src/ohipy
UNUSED_LAYERS = ["rgn_area_inland1mn", "rgn_area_offshore3mn"]


def read_csv_dicts(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def build_rows() -> list[dict]:
    layers = read_csv_dicts(LAYERS_CSV)
    goals = read_csv_dicts(GOALS_CSV)
    pmatrix = read_csv_dicts(PRESSURES_MATRIX)
    rmatrix = read_csv_dicts(RESILIENCE_MATRIX)
    config = yaml.safe_load(CONFIG_YAML.read_text())

    layer_name = {l["layer"]: l["name"] for l in layers}
    goal_name = {g["goal"]: g["name"] for g in goals}

    rows: list[dict] = []

    def add(goal: str, layer: str, role: str, weight: str = "", detail: str = "", source: str = ""):
        rows.append(
            {
                "goal": goal,
                "goal_name": goal_name.get(goal, ""),
                "layer": layer,
                "layer_name": layer_name.get(layer, ""),
                "role": role,
                "weight": weight,
                "detail": detail,
                "source": source,
            }
        )

    # 1. Direct status/trend/other layers named by a goal in layers.csv `targets`.
    generic_targets = {"pressure", "resilience", "weight", "spatial", "CW pressure"}
    for l in layers:
        target = l["targets"]
        if target in generic_targets:
            continue
        add(target, l["layer"], "status/trend", source="layers.csv:targets")

    # 2. Pressure layers, via the goal x layer matrix. Cell value (1-3) is the
    # pressure category weight (see data/conf/pressure_categories.csv).
    pressure_layer_cols = [k for k in pmatrix[0].keys() if k not in ("goal", "element", "element_name")]
    for r in pmatrix:
        goal, elem = r["goal"], r["element"]
        if not goal:
            continue
        for col in pressure_layer_cols:
            v = r[col].strip()
            if v:
                add(goal, col, "pressure", weight=v, detail=elem, source="pressures_matrix.csv")

    # 3. Resilience layers, via the goal x layer matrix. Cell value is "x"/"".
    resilience_layer_cols = [k for k in rmatrix[0].keys() if k not in ("goal", "element", "element_name")]
    for r in rmatrix:
        goal, elem = r["goal"], r["element"]
        if not goal:
            continue
        for col in resilience_layer_cols:
            if r[col].strip() == "x":
                add(goal, col, "resilience", detail=elem, source="resilience_matrix.csv")

    # 4. Generic element-weighting layers (targets == "weight"), resolved per
    # goal via config.yaml element_mappings.
    element_mappings = config.get("element_mappings", {})
    for role_key, role_label in (("resilience", "resilience element weight"), ("pressures", "pressure element weight")):
        for goal, layer in element_mappings.get(role_key, {}).items():
            add(goal, layer, role_label, source="config.yaml:element_mappings")

    # 5. Code-only links not expressed in any csv/yaml config.
    for goal, layer, role, detail in CODE_ONLY_LINKS:
        add(goal, layer, role, detail=detail, source="src/ohipy/goals (grep)")

    # 6. Layers present in layers.csv but unused by any src/ohipy code path.
    for layer in UNUSED_LAYERS:
        add("", layer, "unused (not referenced in src/ohipy)", source="grep src/ohipy")

    rows.sort(key=lambda r: (r["goal"], r["layer"], r["role"]))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output CSV path (default: stdout)")
    args = parser.parse_args()

    rows = build_rows()
    fieldnames = ["goal", "goal_name", "layer", "layer_name", "role", "weight", "detail", "source"]

    out = args.output.open("w", newline="") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.output:
            out.close()


if __name__ == "__main__":
    main()
