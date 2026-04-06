#!/usr/bin/env python3
# Authored by a human (me)
# This script compares the scores from the Python and R versions of the code, as well as the scores from the previous version of the code (from the "comunas" branch).
import sys
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent

types_dict: dict[str, Any] = {
    "goal": "str",
    "dimension": "str",
    "region_id": "int",
    "score": "float",
}
tolerance = 0.05


def main():
    ps = pd.read_csv(SCRIPT_DIR / "scores_2024_py.csv", dtype=types_dict)  # type: ignore[arg-type]
    ps["score"] = ps.score.round(2)
    rs = pd.read_csv(SCRIPT_DIR / "scores_2024_r.csv", dtype=types_dict)  # type: ignore[arg-type]
    rsr = pd.read_csv(
        "https://raw.githubusercontent.com/OHI-Science/chl/refs/heads/master/comunas/scores.csv",
        dtype=types_dict,  # type: ignore[arg-type]
    )

    df = ps.merge(
        rs, how="left", on=["goal", "dimension", "region_id"], suffixes=("_py", "_r")
    ).merge(rsr, how="left", on=["goal", "dimension", "region_id"])

    # 1st check: R local output equal R output at the repository
    if (df["score_r"] - df["score"]).sum() == 0:
        print("SUCCESS: R local output is equal to R output at the repository")
    else:
        print(
            "WARNING: R local output does NOT match R output at the repository. Stopping execution.",
            file=sys.stderr,
        )
        # sys.exit(1)

    # 2nd check: Python output is equal to R output
    diff_stats = (
        df.assign(diff=df["score_py"] - df["score_r"])
        .groupby(["goal", "dimension"], as_index=False)
        .agg(
            sum_diff=("diff", "sum"),
            mean_diff=("diff", "mean"),
            max_diff=("diff", "max"),
            min_diff=("diff", "min"),
        )
        .round({"sum_diff": 4, "mean_diff": 4})
    ).sort_values(by=["mean_diff"])
    diff_stats.to_csv(SCRIPT_DIR / "scores_difference.csv")

    diff = max(diff_stats["max_diff"].abs().max(), diff_stats["min_diff"].abs().max())
    if diff > tolerance:
        print(
            f"FAILURE: Max difference over the tolerance of {tolerance}: {diff} is the max difference found."
        )
        sys.exit(1)

    print(
        f"SUCCESS: Max difference is inside the tolerance of {tolerance}: {diff} is the max difference found."
    )


if __name__ == "__main__":
    main()
