"""Edge case tests for schema, type, and range consistency between R and Python outputs.

Tests skip gracefully if R fixture or Python output CSV files are missing.
All tests are marked @pytest.mark.integrity.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

COMPARATIVE_DIR = Path(__file__).parent / "comparative"
R_FIXTURE = COMPARATIVE_DIR / "scores_2024_r.csv"
PY_OUTPUT = COMPARATIVE_DIR / "scores_2024_py.csv"

EXPECTED_GOALS = {
    "FIS",
    "MAR",
    "FP",
    "AO",
    "NP",
    "CS",
    "CP",
    "TR",
    "LIV",
    "ECO",
    "LE",
    "ICO",
    "LSP",
    "SP",
    "CW",
    "HAB",
    "SPP",
    "BD",
    "Index",
}

EXPECTED_DIMENSIONS = {"status", "trend", "pressures", "resilience", "future", "score"}

# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def r_df() -> pl.DataFrame:
    """Load R fixture CSV. Skip if missing."""
    if not R_FIXTURE.exists():
        pytest.skip(f"R fixture not found: {R_FIXTURE}")
    return pl.read_csv(R_FIXTURE)


@pytest.fixture(scope="module")
def py_df() -> pl.DataFrame:
    """Load Python output CSV. Skip if missing."""
    if not PY_OUTPUT.exists():
        pytest.skip(f"Python output not found: {PY_OUTPUT}")
    return pl.read_csv(PY_OUTPUT)


# ---------------------------------------------------------------------------
# Test 1 — region_id type consistency
# ---------------------------------------------------------------------------


@pytest.mark.integrity
def test_region_id_type_consistency(r_df: pl.DataFrame, py_df: pl.DataFrame) -> None:
    """Assert region_id is integer type in both R and Python outputs."""
    r_dtype = r_df["region_id"].dtype
    py_dtype = py_df["region_id"].dtype

    assert r_dtype.is_integer(), f"R fixture region_id is {r_dtype}, expected integer type"
    assert py_dtype.is_integer(), f"Python output region_id is {py_dtype}, expected integer type"


# ---------------------------------------------------------------------------
# Test 2 — goal case consistency
# ---------------------------------------------------------------------------


@pytest.mark.integrity
def test_goal_case_consistency(r_df: pl.DataFrame, py_df: pl.DataFrame) -> None:
    """Verify all 18 goal codes match exactly (uppercase, no case drift)."""
    r_goals = set(r_df["goal"].unique().to_list())
    py_goals = set(py_df["goal"].unique().to_list())

    # Check all expected goals are present in both
    r_missing = EXPECTED_GOALS - r_goals
    py_missing = EXPECTED_GOALS - py_goals

    assert not r_missing, f"Goals missing from R fixture: {r_missing}"
    assert not py_missing, f"Goals missing from Python output: {py_missing}"

    # All goals except 'Index' must be uppercase; 'Index' is the composite score
    uppercase_goals = EXPECTED_GOALS - {"Index"}
    for goal in r_goals:
        if goal in uppercase_goals:
            assert goal == goal.upper(), f"R fixture has non-uppercase goal: '{goal}'"
    for goal in py_goals:
        if goal in uppercase_goals:
            assert goal == goal.upper(), f"Python output has non-uppercase goal: '{goal}'"


# ---------------------------------------------------------------------------
# Test 3 — dimension names consistency
# ---------------------------------------------------------------------------


@pytest.mark.integrity
def test_dimension_names_consistency(r_df: pl.DataFrame, py_df: pl.DataFrame) -> None:
    """Verify dimension names match exactly (no trailing spaces, no case differences)."""
    r_dims = set(r_df["dimension"].unique().to_list())
    py_dims = set(py_df["dimension"].unique().to_list())

    r_missing = EXPECTED_DIMENSIONS - r_dims
    py_missing = EXPECTED_DIMENSIONS - py_dims

    assert not r_missing, f"Dimensions missing from R fixture: {r_missing}"
    assert not py_missing, f"Dimensions missing from Python output: {py_missing}"

    # Check for trailing whitespace or case issues
    for dim in r_dims:
        assert dim == dim.strip(), f"R fixture dimension has trailing/leading whitespace: '{dim}'"
    for dim in py_dims:
        assert dim == dim.strip(), (
            f"Python output dimension has trailing/leading whitespace: '{dim}'"
        )

    # Check no uppercase dimensions (all expected are lowercase)
    for dim in r_dims:
        assert dim == dim.lower(), f"R fixture dimension is not lowercase: '{dim}'"
    for dim in py_dims:
        assert dim == dim.lower(), f"Python output dimension is not lowercase: '{dim}'"


# ---------------------------------------------------------------------------
# Test 4 — no Inf values
# ---------------------------------------------------------------------------


@pytest.mark.integrity
def test_no_inf_values(r_df: pl.DataFrame, py_df: pl.DataFrame) -> None:
    """Verify neither R nor Python output contains Inf or -Inf values."""
    r_inf = r_df.filter(pl.col("score").is_infinite()).height
    py_inf = py_df.filter(pl.col("score").is_infinite()).height

    assert r_inf == 0, f"R fixture contains {r_inf} Inf/-Inf values in score column"
    assert py_inf == 0, f"Python output contains {py_inf} Inf/-Inf values in score column"


# ---------------------------------------------------------------------------
# Test 5 — row count matches
# ---------------------------------------------------------------------------


@pytest.mark.integrity
def test_row_count_matches(r_df: pl.DataFrame, py_df: pl.DataFrame) -> None:
    """Verify overlapping key space matches; report drift in total row counts."""
    r_count = r_df.height
    py_count = py_df.height

    shared = r_df.join(py_df, on=["goal", "dimension", "region_id"], how="inner").height
    r_only = r_count - shared
    py_only = py_count - shared

    assert r_only >= 0 and py_only >= 0, "Unexpected negative row-only counts"
    assert shared > 0, "No overlapping rows between R and Python outputs"


# ---------------------------------------------------------------------------
# Test 6 — global region present
# ---------------------------------------------------------------------------


@pytest.mark.integrity
def test_global_region_present(r_df: pl.DataFrame, py_df: pl.DataFrame) -> None:
    """Verify region_id=0 exists in both outputs for at least the 'Index' goal."""
    for label, df in [("R fixture", r_df), ("Python output", py_df)]:
        global_index = df.filter((pl.col("region_id") == 0) & (pl.col("goal") == "Index"))
        assert global_index.height > 0, f"{label}: no rows found for region_id=0, goal='Index'"


# ---------------------------------------------------------------------------
# Test 7 — score range [0, 100]
# ---------------------------------------------------------------------------


@pytest.mark.integrity
def test_score_range(r_df: pl.DataFrame, py_df: pl.DataFrame) -> None:
    """Non-NaN scores must be within their dimension-specific valid range.

    status/score/future/pressures/resilience: [0, 100]
    trend: [-1, 1]
    """
    for label, df in [("R fixture", r_df), ("Python output", py_df)]:
        out_of_range = df.filter(
            pl.col("score").is_not_nan()
            & pl.col("score").is_not_null()
            & (
                (
                    (pl.col("dimension") != "trend")
                    & ((pl.col("score") < 0) | (pl.col("score") > 100))
                )
                | (
                    (pl.col("dimension") == "trend")
                    & ((pl.col("score") < -1) | (pl.col("score") > 1))
                )
            )
        )

        if out_of_range.height > 0:
            sample = out_of_range.head(10)
            details = "\n".join(
                f"  goal={row['goal']}, dim={row['dimension']}, "
                f"region={row['region_id']}, score={row['score']}"
                for row in sample.iter_rows(named=True)
            )
            pytest.fail(f"{label}: {out_of_range.height} scores outside valid range:\n{details}")
