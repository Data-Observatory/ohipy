import polars as pl


def pre_global_scores(scores: pl.DataFrame, region_labels: pl.DataFrame) -> pl.DataFrame:
    allowed = region_labels.get_column("rgn_id").to_list() + [0]
    return scores.filter(pl.col("region_id").is_in(allowed))


def finalize_scores(
    scores: pl.DataFrame, region_labels: pl.DataFrame, goals: list[str]
) -> pl.DataFrame:
    dims = ["pressures", "resilience", "status", "trend", "future", "score"]
    all_regions = region_labels.get_column("rgn_id").to_list() + [0]
    all_goals = goals + ["Index"]

    goals_df = pl.DataFrame({"goal": all_goals})
    dims_df = pl.DataFrame({"dimension": dims})
    regions_df = pl.DataFrame({"region_id": all_regions}).with_columns(
        pl.col("region_id").cast(pl.Int64)
    )

    full = goals_df.join(dims_df, how="cross").join(regions_df, how="cross")

    invalid_condition = (
        (
            pl.col("dimension").is_in(["pressures", "resilience", "trend"])
            & (pl.col("region_id") == 0)
        )
        | (
            pl.col("dimension").is_in(["pressures", "resilience", "trend", "status"])
            & (pl.col("goal") == "Index")
        )
        | (
            pl.col("dimension").is_in(["pressures", "resilience"])
            & (pl.col("goal").is_in(["BD", "LE", "SP", "FP"]))
        )
    )
    full = full.filter(~invalid_condition)

    # Filter scores to remove invalid combinations before merging
    scores = scores.filter(~invalid_condition)
    scores = scores.with_columns(pl.col("region_id").cast(pl.Int64))

    merged = full.join(scores, on=["goal", "dimension", "region_id"], how="left")
    merged = merged.unique()
    merged = merged.sort(["goal", "dimension", "region_id"])

    merged = merged.with_columns(pl.col("region_id").cast(pl.Int64))

    return merged.select(["goal", "dimension", "region_id", "score"])
