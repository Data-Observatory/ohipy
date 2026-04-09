"""Shared comparison module for R-vs-Python parity testing."""

from typing import NamedTuple

import polars as pl


class ComparisonResult(NamedTuple):
    """Result of comparing Python and R scores."""

    max_diff: float
    failure_count: int
    py_missing_count: int
    r_missing_count: int
    nan_mismatch_count: int
    failures_df: pl.DataFrame
    summary_df: pl.DataFrame


def _assert_key_uniqueness(df: pl.DataFrame, join_cols: list[str], name: str) -> None:
    """Assert that join columns form unique keys. Raise AssertionError if not."""
    duplicates = df.group_by(join_cols).len().filter(pl.col("len") > 1)
    if duplicates.height > 0:
        dupes = duplicates.head(5)
        lines = [f"Duplicate keys in {name}:"]
        for row in dupes.iter_rows(named=True):
            key_str = ", ".join(str(row[c]) for c in join_cols)
            lines.append(f"  {key_str}: {row['len']} occurrences")
        raise AssertionError("\n".join(lines))


def compare_scores(
    py_scores: pl.DataFrame,
    r_scores: pl.DataFrame,
    tolerance: float = 0.01,
    join_cols: list[str] | None = None,
) -> ComparisonResult:
    """
    Compare Python and R scores using outer join with full NaN handling.

    Parameters
    ----------
    py_scores : pl.DataFrame
        Python scores with columns [region_id, goal, dimension, score]
    r_scores : pl.DataFrame
        R scores with columns [region_id, goal, dimension, score]
    tolerance : float
        Maximum allowed absolute difference for non-NaN values
    join_cols : list[str] | None
        Columns to join on. Defaults to ["region_id", "goal", "dimension"]

    Returns
    -------
    ComparisonResult
        NamedTuple with max_diff, failure_count, missing counts, and failure details
    """
    if join_cols is None:
        join_cols = ["region_id", "goal", "dimension"]

    # Assert key uniqueness on both DataFrames
    _assert_key_uniqueness(py_scores, join_cols, "Python scores")
    _assert_key_uniqueness(r_scores, join_cols, "R scores")

    # Round scores to 2 decimal places
    py_df = py_scores.with_columns(pl.col("score").round(2))
    r_df = r_scores.with_columns(pl.col("score").round(2))

    # Outer join on join_cols
    merged = py_df.join(r_df, on=join_cols, how="full", suffix="_r")

    # Coalesce join keys (polars full join creates nulls for unmatched sides)
    for col in join_cols:
        merged = merged.with_columns(pl.col(col).fill_null(pl.col(f"{col}_r")).alias(col)).drop(
            f"{col}_r"
        )

    # Detect missing rows
    py_missing_count = merged.filter(pl.col("score").is_null()).height
    r_missing_count = merged.filter(pl.col("score_r").is_null()).height

    # For matched rows, classify each comparison
    matched = merged.filter(pl.col("score").is_not_null() & pl.col("score_r").is_not_null())

    # Build diff column for matched rows
    matched = matched.with_columns((pl.col("score") - pl.col("score_r")).abs().alias("diff"))

    # NaN mismatch: exactly one side is NaN
    nan_mismatch_count = matched.filter(
        (pl.col("score").is_nan() & ~pl.col("score_r").is_nan())
        | (~pl.col("score").is_nan() & pl.col("score_r").is_nan())
    ).height

    # Value difference for non-NaN pairs
    value_diffs = matched.filter(
        (~pl.col("score").is_nan())
        .and_(~pl.col("score_r").is_nan())
        .and_(pl.col("diff") > tolerance)
    )

    # Collect failures with failure_type
    failures_list: list[dict] = []

    # py_missing: score is null (present in R only)
    if py_missing_count > 0:
        py_missing = merged.filter(pl.col("score").is_null())
        for row in py_missing.iter_rows(named=True):
            failures_list.append(
                {
                    "region_id": row["region_id"],
                    "goal": row["goal"],
                    "dimension": row["dimension"],
                    "score_py": None,
                    "score_r": row["score_r"],
                    "diff": None,
                    "failure_type": "py_missing",
                }
            )

    # r_missing: score_r is null (present in Python only)
    if r_missing_count > 0:
        r_missing = merged.filter(pl.col("score_r").is_null())
        for row in r_missing.iter_rows(named=True):
            failures_list.append(
                {
                    "region_id": row["region_id"],
                    "goal": row["goal"],
                    "dimension": row["dimension"],
                    "score_py": row["score"],
                    "score_r": None,
                    "diff": None,
                    "failure_type": "r_missing",
                }
            )

    # nan_mismatch
    nan_mismatches = matched.filter(
        (pl.col("score").is_nan() & ~pl.col("score_r").is_nan())
        | (~pl.col("score").is_nan() & pl.col("score_r").is_nan())
    )
    for row in nan_mismatches.iter_rows(named=True):
        score_py = row["score"]
        score_r = row["score_r"]
        failures_list.append(
            {
                "region_id": row["region_id"],
                "goal": row["goal"],
                "dimension": row["dimension"],
                "score_py": float(score_py)
                if not (score_py is None or str(score_py) == "nan")
                else None,
                "score_r": float(score_r)
                if not (score_r is None or str(score_r) == "nan")
                else None,
                "diff": None,
                "failure_type": "nan_mismatch",
            }
        )

    # value_diff
    for row in value_diffs.iter_rows(named=True):
        failures_list.append(
            {
                "region_id": row["region_id"],
                "goal": row["goal"],
                "dimension": row["dimension"],
                "score_py": row["score"],
                "score_r": row["score_r"],
                "diff": row["diff"],
                "failure_type": "value_diff",
            }
        )

    # Build failures DataFrame
    if failures_list:
        failures_df = pl.DataFrame(failures_list)
    else:
        failures_df = pl.DataFrame(
            {
                "region_id": pl.Series([], dtype=pl.Int64),
                "goal": pl.Series([], dtype=pl.String),
                "dimension": pl.Series([], dtype=pl.String),
                "score_py": pl.Series([], dtype=pl.Float64),
                "score_r": pl.Series([], dtype=pl.Float64),
                "diff": pl.Series([], dtype=pl.Float64),
                "failure_type": pl.Series([], dtype=pl.String),
            }
        )

    # Build summary by (dimension, goal)
    if failures_df.height > 0:
        summary_df = (
            failures_df.group_by(["dimension", "goal"])
            .agg(
                pl.len().alias("count"),
                pl.col("diff").max().alias("max_diff"),
            )
            .sort("max_diff", descending=True)
        )
    else:
        summary_df = pl.DataFrame(
            {
                "dimension": pl.Series([], dtype=pl.String),
                "goal": pl.Series([], dtype=pl.String),
                "count": pl.Series([], dtype=pl.Int64),
                "max_diff": pl.Series([], dtype=pl.Float64),
            }
        )

    # Compute max_diff across all matched non-NaN non-null pairs
    valid_diffs = matched.filter(
        pl.col("score").is_not_null()
        & pl.col("score_r").is_not_null()
        & ~pl.col("score").is_nan()
        & ~pl.col("score_r").is_nan()
    )["diff"]
    max_diff = float(valid_diffs.max()) if len(valid_diffs) > 0 else 0.0  # type: ignore[arg-type]

    failure_count = len(failures_list)

    return ComparisonResult(
        max_diff=max_diff,
        failure_count=failure_count,
        py_missing_count=py_missing_count,
        r_missing_count=r_missing_count,
        nan_mismatch_count=nan_mismatch_count,
        failures_df=failures_df,
        summary_df=summary_df,
    )


def format_failure_report(
    result: ComparisonResult,
    dataset: str | None = None,
    variation: str | None = None,
) -> str:
    """
    Format a human-readable failure report from a ComparisonResult.

    Parameters
    ----------
    result : ComparisonResult
        The comparison result to format
    dataset : str | None
        Optional dataset name to include in report
    variation : str | None
        Optional variation name to include in report

    Returns
    -------
    str
        Formatted failure report string
    """
    lines: list[str] = []

    header = f"PARITY FAILURE: {result.failure_count} scores differ"
    lines.append(header)

    if dataset or variation:
        parts = []
        if dataset:
            parts.append(f"Dataset: {dataset}")
        if variation:
            parts.append(f"Variation: {variation}")
        lines.append(", ".join(parts))

    missing_info = (
        f"Missing from Python: {result.py_missing_count} | "
        f"Missing from R: {result.r_missing_count} | "
        f"NaN mismatches: {result.nan_mismatch_count}"
    )
    lines.append(missing_info)

    lines.append("")
    lines.append("Failures by dimension then goal:")

    # Show top 10 failures
    top_failures = result.summary_df.head(10)
    for row in top_failures.iter_rows(named=True):
        dim = row["dimension"]
        goal = row["goal"]
        count = row["count"]
        max_diff = row["max_diff"]
        if max_diff is not None:
            lines.append(f"  {dim:10s} / {goal:6s}: count={count}, max_diff={max_diff:.4f}")
        else:
            lines.append(f"  {dim:10s} / {goal:6s}: count={count}, max_diff=N/A")

    lines.append("")
    lines.append(f"Max absolute difference: {result.max_diff}")

    return "\n".join(lines)


def assert_parity(
    result: ComparisonResult,
    dataset: str | None = None,
    variation: str | None = None,
) -> None:
    """
    Assert that Python and R scores are in parity.

    Parameters
    ----------
    result : ComparisonResult
        The comparison result to check
    dataset : str | None
        Optional dataset name for error messages
    variation : str | None
        Optional variation name for error messages

    Raises
    ------
    AssertionError
        If any failures were found in the comparison
    """
    if result.failure_count > 0:
        report = format_failure_report(result, dataset=dataset, variation=variation)
        raise AssertionError(report)
