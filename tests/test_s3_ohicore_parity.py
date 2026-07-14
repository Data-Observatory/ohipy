"""ohipy vs Docker-ohi-core equivalence on the S3 s3_2026.v01 assessment layers.

NOT for CI/CD (all tests marked ``s3_parity``; CI runs ``-m "not ... and not s3_parity"``).
Run manually:
    uv run pytest tests/test_s3_ohicore_parity.py -m s3_parity -v

Default flow is fully offline: recompute ohipy scores on the committed scenario layers+conf
(tests/comparative/scenarios/s3_2026.v01/) and compare against the committed R reference
(tests/comparative/fixtures/s3_2026.v01/baseline.csv). Setting OHI_AUTO_GENERATE_FIXTURES=1
regenerates the R reference (needs Docker + already-downloaded S3 parquet).

`test_full_equivalence` is a tracked parity gate: it is `xfail(strict=True)` because ohipy and
ohi-core currently diverge on TR/LE/LIV and the propagated Index. It XFAILs today; once the
engine reaches full parity it will XPASS and (via strict) fail, prompting removal of the xfail
marker (promotion to a required PASS). The other two tests are data-health checks that pass now.
"""

from __future__ import annotations

import os
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.s3_parity

from tests.helpers.comparison import assert_parity, compare_scores
from tests.parity import s3_fixture

TOLERANCE = 0.01
AUTO_GEN = os.environ.get("OHI_AUTO_GENERATE_FIXTURES", "") == "1"
# Already-downloaded S3 parquet used only when regenerating (S3 pull is done out-of-band).
_DEFAULT_PARQUET = Path(f"/tmp/ohipy_s3_layers_{s3_fixture.SCENARIO}")


def _pressures(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter(pl.col("dimension") == "pressures")


def _all_pressures_100(df: pl.DataFrame) -> bool:
    """True only if EVERY pressures score rounds to >= 100 (the catastrophic all-maxed case)."""
    p = _pressures(df)
    if p.is_empty():
        return False
    return bool(p.select((pl.col("score").round(2) >= 100).all()).item())


@pytest.fixture(scope="module")
def scores() -> tuple[pl.DataFrame, pl.DataFrame]:
    """(ohipy_scores, r_scores) for the s3_2026.v01 scenario."""
    if not s3_fixture.fixture_exists():
        if AUTO_GEN:
            parquet_dir = Path(os.environ.get("S3_PARQUET_DIR", _DEFAULT_PARQUET))
            if not parquet_dir.exists():
                pytest.skip(
                    f"OHI_AUTO_GENERATE_FIXTURES=1 but no downloaded parquet at {parquet_dir} "
                    "(run proj-IDEOS-metas/scripts/sync_from_s3.sh first, or set S3_PARQUET_DIR)"
                )
            s3_fixture.regenerate(parquet_dir)
        else:
            pytest.skip(
                "committed s3_2026.v01 fixture missing; "
                "set OHI_AUTO_GENERATE_FIXTURES=1 to regenerate"
            )
    return s3_fixture.run_ohipy_offline(), s3_fixture.load_r_fixture()


@pytest.mark.xfail(
    strict=True,
    reason="ohipy TR/LE/LIV/Index not yet at parity with ohi-core; remove this marker when fixed",
)
def test_full_equivalence(scores: tuple[pl.DataFrame, pl.DataFrame]) -> None:
    """STRICT: every goal must match ohi-core within tolerance (no whitelist)."""
    ohipy_scores, r_scores = scores
    result = compare_scores(ohipy_scores, r_scores, tolerance=TOLERANCE)
    assert_parity(result)


def test_pressures_not_all_100(scores: tuple[pl.DataFrame, pl.DataFrame]) -> None:
    """Data health: the pressures dimension must NOT be entirely 100 (all-maxed => bug)."""
    ohipy_scores, r_scores = scores
    assert not _all_pressures_100(r_scores), "R fixture: all pressures scores are 100"
    assert not _all_pressures_100(ohipy_scores), "ohipy: all pressures scores are 100"


def test_pressures_resilience_identical(scores: tuple[pl.DataFrame, pl.DataFrame]) -> None:
    """The pressures and resilience dimensions must be identical between ohipy and ohi-core."""
    ohipy_scores, r_scores = scores
    dims = ["pressures", "resilience"]
    result = compare_scores(
        ohipy_scores.filter(pl.col("dimension").is_in(dims)),
        r_scores.filter(pl.col("dimension").is_in(dims)),
        tolerance=TOLERANCE,
    )
    assert_parity(result)
