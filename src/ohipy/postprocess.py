import pandas as pd
import numpy as np


def pre_global_scores(scores, region_labels):
    allowed = set(region_labels["rgn_id"].tolist()) | {0}
    return scores[scores["region_id"].isin(allowed)].copy()


def finalize_scores(scores, region_labels, goals):
    dims = ["pressures", "resilience", "status", "trend", "future", "score"]
    all_regions = list(region_labels["rgn_id"].tolist()) + [0]
    all_goals = goals + ["Index"]

    full = pd.MultiIndex.from_product(
        [all_goals, dims, all_regions],
        names=["goal", "dimension", "region_id"],
    ).to_frame(index=False)

    invalid = (
        (
            full["dimension"].isin(["pressures", "resilience", "trend"])
            & (full["region_id"] == 0)
        )
        | (
            full["dimension"].isin(["pressures", "resilience", "trend", "status"])
            & (full["goal"] == "Index")
        )
        | (
            full["dimension"].isin(["pressures", "resilience"])
            & (full["goal"].isin(["BD", "LE", "SP", "FP"]))
        )
    )
    full = full[~invalid]

    # Filter scores to remove invalid combinations before merging
    scores_invalid = (
        (
            scores["dimension"].isin(["pressures", "resilience", "trend"])
            & (scores["region_id"] == 0)
        )
        | (
            scores["dimension"].isin(["pressures", "resilience", "trend", "status"])
            & (scores["goal"] == "Index")
        )
        | (
            scores["dimension"].isin(["pressures", "resilience"])
            & (scores["goal"].isin(["BD", "LE", "SP", "FP"]))
        )
    )
    scores = scores[~scores_invalid]

    merged = scores.merge(full, on=["goal", "dimension", "region_id"], how="outer")
    merged = merged.drop_duplicates()
    merged = merged.sort_values(["goal", "dimension", "region_id"])

    # Ensure region_id is integer (pandas can convert to float during merge with NaNs)
    merged["region_id"] = merged["region_id"].astype("Int64").astype(int)
    
    return merged[["goal", "dimension", "region_id", "score"]].copy()
