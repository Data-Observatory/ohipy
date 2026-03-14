"""Type definitions for ohipy."""

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    import polars as pl


class GoalResult:
    """Result of a goal calculation."""

    status: "pl.DataFrame"
    trend: "pl.DataFrame"
    pressures: "pl.DataFrame | None"
    resilience: "pl.DataFrame | None"

    def __init__(
        self,
        status: "pl.DataFrame",
        trend: "pl.DataFrame",
        pressures: "pl.DataFrame | None" = None,
        resilience: "pl.DataFrame | None" = None,
    ) -> None:
        self.status = status
        self.trend = trend
        self.pressures = pressures
        self.resilience = resilience


ConfigData = dict[str, object]
LayerDict = dict[str, "pl.DataFrame"]


# Override types
class WeightsOverride(TypedDict, total=False):
    """Dictionary mapping goal codes to weight values."""

    __root__: dict[str, float]


class DisableOverride(TypedDict, total=False):
    """Specifies pressures and resiliences to disable."""

    pressures: list[str]
    resiliences: list[str]


class MatricesOverride(TypedDict, total=False):
    """Custom pressure and resilience matrices."""

    pressures: "pl.DataFrame"
    resilience: "pl.DataFrame"


class OverridesConfig(TypedDict, total=False):
    """Combined overrides configuration."""

    weights: dict[str, float]
    disable: DisableOverride
    matrices: MatricesOverride


class StatisticsConfig(TypedDict, total=False):
    """Configuration for which statistics to compute."""

    statistics: list[
        str
    ]  # e.g., ['mean', 'std', 'median', 'p025', 'p975', 'min', 'max', 'count', 'iqr']


# Result types (for documentation/type hints - actual return is DataFrame)
# RunResult: DataFrame with columns [region_id, goal, dimension, score]
# MultiYearResult: DataFrame with columns [region_id, goal, dimension, mean, std, median, p025, p975, min, max, count, iqr]


__all__ = [
    "GoalResult",
    "ConfigData",
    "LayerDict",
    "WeightsOverride",
    "DisableOverride",
    "MatricesOverride",
    "OverridesConfig",
    "StatisticsConfig",
]
