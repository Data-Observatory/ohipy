"""API parity tests — validate Lambda API against local ohipy calculations.

NOT for CI/CD. Requires network access to the OHI Lambda API.
Run manually: uv run pytest tests/test_api_parity.py -v
"""

import io
import json
import logging
import urllib.request
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.api

from ohipy.config import load_config
from ohipy.layers import load_layers
from ohipy.runner import OHIRunner
from ohipy.types import OverridesConfig
from tests.helpers.comparison import assert_parity, compare_scores

# --- Constants ---
API_URL = "https://2nz7klga83.execute-api.us-east-1.amazonaws.com/v1/ohi/scores"
YEAR = 2024
TOLERANCE = 0.01
LOG_FILE = Path(__file__).parent / "api_parity.log"
PREVIEW_ROWS = 50

# --- Logging ---
logger = logging.getLogger("api_parity")
logger.setLevel(logging.DEBUG)


def _setup_logging() -> None:
    """Configure file logger (idempotent — safe to call multiple times)."""
    if logger.handlers:
        return
    fh = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(fh)


_setup_logging()


def _df_preview(df: pl.DataFrame, n: int = PREVIEW_ROWS) -> str:
    with io.StringIO() as buf:
        buf.write(f"shape: {df.shape}\n")
        df.head(n).write_csv(buf)
        return buf.getvalue()


def _log_section(title: str, body: str) -> None:
    logger.info(f"\n{'=' * 60}")
    logger.info(f"  {title}")
    logger.info(f"{'=' * 60}")
    logger.info(body)


# --- Helpers ---


def call_api(
    weights: dict[str, float] | None = None,
    pressures: list[dict[str, list[str]]] | None = None,
    resiliences: list[dict[str, list[str]]] | None = None,
    *,
    test_name: str = "",
) -> pl.DataFrame:
    """Call the OHI Lambda API and return scores as a Polars DataFrame.

    Args:
        weights: Dict mapping goal codes to weight values (e.g. {"FIS": 2.0}).
        pressures: List of category-dicts specifying pressure layers to REMOVE.
            e.g. [{"p_climateChange": ["cc_anomaliast", "cc_sataragonita"]}]
        resiliences: Same format as pressures, for resilience layers to REMOVE.
        test_name: Name of the calling test (used for log section headers).

    Returns:
        DataFrame with columns [region_id, goal, dimension, score].
    """
    config = {
        "goalSubgoalWeight": weights or {},
        "pressures": pressures or [],
        "resiliences": resiliences or [],
        "sensibility": {"repeat": 500, "results": 1},
    }

    payload = {
        "scenarios": [
            {
                "filters": {
                    "year": str(YEAR),
                    "regionIds": [],
                    "goalSubgoal": "",
                    "dimension": "",
                },
                "config": config,
            }
        ]
    }

    _log_section(f"API CALL — {test_name}", json.dumps(payload, indent=2))

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    scores_list = data["scenarios"][0]["scores"]
    df = pl.DataFrame(
        scores_list,
        schema={
            "goal": pl.String,
            "dimension": pl.String,
            "region_id": pl.Int64,
            "score": pl.Float64,
        },
    )

    _log_section(f"API RESPONSE — {test_name}", _df_preview(df))

    return df


def run_local(
    runner: OHIRunner,
    layers_data: dict[str, pl.DataFrame],
    weights: dict[str, float] | None = None,
    disable_pressures: list[str] | None = None,
    disable_resiliences: list[str] | None = None,
    *,
    test_name: str = "",
) -> pl.DataFrame:
    """Run local ohipy calculation with given overrides.

    Args:
        runner: OHIRunner instance.
        layers_data: Layers data dict (layers["data"]).
        weights: Dict mapping goal codes to weight values.
        disable_pressures: Flat list of pressure column names to disable.
        disable_resiliences: Flat list of resilience column names to disable.
        test_name: Name of the calling test (used for log section headers).

    Returns:
        DataFrame with columns [region_id, goal, dimension, score].
    """
    overrides: OverridesConfig = {}
    if weights:
        overrides["weights"] = weights
    if disable_pressures or disable_resiliences:
        overrides["disable"] = {
            "pressures": disable_pressures or [],
            "resiliences": disable_resiliences or [],
        }

    params = {
        "year": YEAR,
        "weights": weights,
        "disable_pressures": disable_pressures,
        "disable_resiliences": disable_resiliences,
    }
    _log_section(f"LOCAL CALL — {test_name}", json.dumps(params, indent=2, default=str))

    df = runner.run(year=YEAR, layers=layers_data, overrides=overrides or None)

    _log_section(f"LOCAL RESULT — {test_name}", _df_preview(df))

    return df


def flatten_api_layers(category_list: list[dict[str, list[str]]]) -> list[str]:
    """Flatten API category-grouped layer lists into a flat list.

    Example:
        [{"p_climateChange": ["cc_anomaliast", "cc_sataragonita"]}]
        -> ["cc_anomaliast", "cc_sataragonita"]
    """
    result: list[str] = []
    for category_dict in category_list:
        for layer_names in category_dict.values():
            result.extend(layer_names)
    return result


# --- Fixtures (module-scoped for efficiency) ---


@pytest.fixture(scope="module")
def runner() -> OHIRunner:
    """Create OHIRunner instance (loads config once)."""
    return OHIRunner()


@pytest.fixture(scope="module")
def layers_data() -> dict[str, pl.DataFrame]:
    """Load layers data once for all tests."""
    config = load_config()
    layers = load_layers(config)
    return layers["data"]


# --- Test Cases ---


def test_baseline(runner: OHIRunner, layers_data: dict[str, pl.DataFrame]) -> None:
    """Baseline: no overrides — API and local should produce identical scores."""
    api_scores = call_api(test_name="test_baseline")
    local_scores = run_local(runner, layers_data, test_name="test_baseline")

    result = compare_scores(local_scores, api_scores, tolerance=TOLERANCE)
    assert_parity(result, dataset="baseline")


def test_weight_modification(
    runner: OHIRunner, layers_data: dict[str, pl.DataFrame]
) -> None:
    """Weight modification: FIS=2.0, MAR=0.5 — scores should change identically."""
    weights = {"FIS": 2.0, "MAR": 0.5}

    api_scores = call_api(weights=weights, test_name="test_weight_modification")
    local_scores = run_local(
        runner, layers_data, weights=weights, test_name="test_weight_modification"
    )

    result = compare_scores(local_scores, api_scores, tolerance=TOLERANCE)
    assert_parity(result, dataset="weight_modification")


def test_pressure_removal(
    runner: OHIRunner, layers_data: dict[str, pl.DataFrame]
) -> None:
    """Pressure removal: disable climate change pressures."""
    pressures_to_remove = [{"p_climateChange": ["cc_anomaliast", "cc_sataragonita"]}]

    api_scores = call_api(pressures=pressures_to_remove, test_name="test_pressure_removal")
    flat = flatten_api_layers(pressures_to_remove)
    local_scores = run_local(
        runner, layers_data, disable_pressures=flat, test_name="test_pressure_removal"
    )

    result = compare_scores(local_scores, api_scores, tolerance=TOLERANCE)
    assert_parity(result, dataset="pressure_removal")


def test_resilience_removal(
    runner: OHIRunner, layers_data: dict[str, pl.DataFrame]
) -> None:
    """Resilience removal: disable regulatory fishing resiliences."""
    resiliences_to_remove = [{"r_regulatory": ["fsc_pesca", "fsc_acuicultura"]}]

    api_scores = call_api(resiliences=resiliences_to_remove, test_name="test_resilience_removal")
    flat = flatten_api_layers(resiliences_to_remove)
    local_scores = run_local(
        runner, layers_data, disable_resiliences=flat, test_name="test_resilience_removal"
    )

    result = compare_scores(local_scores, api_scores, tolerance=TOLERANCE)
    assert_parity(result, dataset="resilience_removal")


def test_combined_overrides(
    runner: OHIRunner, layers_data: dict[str, pl.DataFrame]
) -> None:
    """Combined: weights + pressure removal + resilience removal."""
    weights = {"FIS": 2.0, "MAR": 0.5}
    pressures_to_remove = [{"p_climateChange": ["cc_anomaliast"]}]
    resiliences_to_remove = [{"r_regulatory": ["fsc_pesca"]}]

    api_scores = call_api(
        weights=weights,
        pressures=pressures_to_remove,
        resiliences=resiliences_to_remove,
        test_name="test_combined_overrides",
    )
    flat_pressures = flatten_api_layers(pressures_to_remove)
    flat_resiliences = flatten_api_layers(resiliences_to_remove)
    local_scores = run_local(
        runner,
        layers_data,
        weights=weights,
        disable_pressures=flat_pressures,
        disable_resiliences=flat_resiliences,
        test_name="test_combined_overrides",
    )

    result = compare_scores(local_scores, api_scores, tolerance=TOLERANCE)
    assert_parity(result, dataset="combined_overrides")
