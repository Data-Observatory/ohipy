import polars as pl


def LE(scores: pl.DataFrame, layers: object) -> pl.DataFrame:  # noqa: N802
    _ = layers

    le_scores = scores.filter(
        pl.col("goal").is_in(["LIV", "ECO"])
        & pl.col("dimension").is_in(["status", "trend", "future", "score"])
    )

    le_scores = (
        le_scores.group_by(["region_id", "dimension"])
        .agg(pl.col("score").mean())
        .with_columns(pl.lit("LE").alias("goal"))
        .select(["goal", "dimension", "region_id", "score"])
    )

    return pl.concat(
        [scores.select(["goal", "dimension", "region_id", "score"]), le_scores],
        how="vertical_relaxed",
    )
