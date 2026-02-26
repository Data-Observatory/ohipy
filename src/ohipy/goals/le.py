import pandas as pd


def LE(scores, layers):
    le_scores = scores[
        scores["goal"].isin(["LIV", "ECO"])
        & scores["dimension"].isin(["status", "trend", "future", "score"])
    ]

    le_scores = (
        le_scores.groupby(["region_id", "dimension"], as_index=False)["score"]
        .mean()
        .assign(goal="LE")
    )

    le_scores = le_scores[["region_id", "goal", "dimension", "score"]]

    # R behavior in ohi-science-chl/comunas/conf/functions.R duplicates existing
    # scores when returning LE: s <- rbind(scores, LE); return(rbind(scores, s)).
    # This was fixed on 2026-02-26, as per agreement with R code author, to only append once.
    scores_updated = pd.concat([scores, le_scores], ignore_index=True)
    return scores_updated
