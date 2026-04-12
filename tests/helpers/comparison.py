"""Shared comparison module for R-vs-Python parity testing."""

import math
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

    # Round scores to 2 decimal places and add presence indicators
    py_df = py_scores.with_columns(
        pl.col("score").round(2),
        pl.lit(True).alias("__py_present"),
    )
    r_df = r_scores.with_columns(
        pl.col("score").round(2),
        pl.lit(True).alias("__r_present"),
    )

    # Outer join on join_cols
    merged = py_df.join(r_df, on=join_cols, how="full", suffix="_r")

    # Coalesce join keys (polars full join creates nulls for unmatched sides)
    for col in join_cols:
        merged = merged.with_columns(pl.col(col).fill_null(pl.col(f"{col}_r")).alias(col)).drop(
            f"{col}_r"
        )

    # Detect missing rows using presence indicators (not score null)
    py_missing_count = merged.filter(pl.col("__py_present").is_null()).height
    r_missing_count = merged.filter(pl.col("__r_present").is_null()).height

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
    # Round diff to 10 decimal places to avoid floating-point precision artifacts
    # at the tolerance boundary (e.g., 0.010000000000005116 when true diff is 0.01)
    matched = matched.with_columns(pl.col("diff").round(10))
    value_diffs = matched.filter(
        (~pl.col("score").is_nan())
        .and_(~pl.col("score_r").is_nan())
        .and_(pl.col("diff") > tolerance)
    )

    # Collect failures with failure_type
    failures_list: list[dict[str, object]] = []

    # py_missing: present in R only
    if py_missing_count > 0:
        py_missing = merged.filter(pl.col("__py_present").is_null())
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

    # r_missing: present in Python only
    if r_missing_count > 0:
        r_missing = merged.filter(pl.col("__r_present").is_null())
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
        py_val: float | None = (
            None if score_py is None or math.isnan(float(score_py)) else float(score_py)
        )
        r_val: float | None = (
            None if score_r is None or math.isnan(float(score_r)) else float(score_r)
        )
        failures_list.append(
            {
                "region_id": row["region_id"],
                "goal": row["goal"],
                "dimension": row["dimension"],
                "score_py": py_val,
                "score_r": r_val,
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

    # Build failures DataFrame with explicit schema to avoid NaN/None type conflicts
    _failures_schema = {
        "region_id": pl.Int64,
        "goal": pl.String,
        "dimension": pl.String,
        "score_py": pl.Float64,
        "score_r": pl.Float64,
        "diff": pl.Float64,
        "failure_type": pl.String,
    }
    if failures_list:
        failures_df = pl.DataFrame(failures_list, schema=_failures_schema)
    else:
        failures_df = pl.DataFrame({k: pl.Series([], dtype=v) for k, v in _failures_schema.items()})

    # Build summary by (dimension, goal), sorted dimension-first then max_diff
    _dimension_order = ["status", "trend", "pressures", "resilience", "future", "score", "Index"]
    if failures_df.height > 0:
        summary_df = (
            failures_df.group_by(["dimension", "goal"])
            .agg(
                pl.len().alias("count"),
                pl.col("diff").max().alias("max_diff"),
            )
            .with_columns(
                pl.col("dimension")
                .map_elements(
                    lambda d: _dimension_order.index(d)
                    if d in _dimension_order
                    else len(_dimension_order),
                    return_dtype=pl.Int64,
                )
                .alias("_dim_order")
            )
            .sort(["_dim_order", "max_diff"], descending=[False, True])
            .drop("_dim_order")
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
    max_val = valid_diffs.max()
    max_diff = float(max_val) if isinstance(max_val, (int, float)) else 0.0

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

    _dimension_order = ["status", "trend", "pressures", "resilience", "future", "score", "Index"]
    if result.summary_df.height > 0:
        dimensions = result.summary_df.get_column("dimension").unique().to_list()
        dimensions_sorted = sorted(
            dimensions,
            key=lambda d: _dimension_order.index(d)
            if d in _dimension_order
            else len(_dimension_order),
        )
        for dim in dimensions_sorted:
            dim_rows = result.summary_df.filter(pl.col("dimension") == dim)
            lines.append(f"  Dimension: {dim}")
            for row in dim_rows.iter_rows(named=True):
                goal = row["goal"]
                count = row["count"]
                max_diff = row["max_diff"]
                if max_diff is not None:
                    lines.append(f"    {goal:6s}: count={count}, max_diff={max_diff:.4f}")
                else:
                    lines.append(f"    {goal:6s}: count={count}, max_diff=N/A")
    else:
        lines.append("  (none)")

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
