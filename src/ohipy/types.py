"""Type definitions for ohipy."""

from typing import Any

import pandas as pd


class GoalResult:
    """Result of a goal calculation."""

    def __init__(
        self,
        status: pd.DataFrame,
        trend: pd.DataFrame,
        pressures: pd.DataFrame | None = None,
        resilience: pd.DataFrame | None = None,
    ) -> None:
        self.status = status
        self.trend = trend
        self.pressures = pressures
        self.resilience = resilience


ConfigData = dict[str, Any]
LayerDict = dict[str, pd.DataFrame]


__all__ = ["GoalResult", "ConfigData", "LayerDict"]
