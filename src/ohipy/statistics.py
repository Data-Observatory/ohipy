"""Streaming statistics accumulator using numpy.

Provides efficient computation of common statistics on accumulated values.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import numpy.typing as npt

__all__ = ["StatisticsAccumulator", "SUPPORTED_STATISTICS"]

SUPPORTED_STATISTICS = Literal[
    "mean", "std", "median", "p025", "p975", "min", "max", "count", "iqr"
]

ALL_STATISTICS: list[SUPPORTED_STATISTICS] = [
    "mean",
    "std",
    "median",
    "p025",
    "p975",
    "min",
    "max",
    "count",
    "iqr",
]


class StatisticsAccumulator:
    """Accumulator for computing streaming statistics on numeric values.

    Stores all values in memory and computes statistics on demand.
    Supports configurable subset of statistics.

    Example:
        >>> acc = StatisticsAccumulator()
        >>> acc.add([1.0, 2.0, 3.0, 4.0, 5.0])
        >>> result = acc.compute()
        >>> print(result["mean"])
        3.0
    """

    def __init__(self, statistics: list[SUPPORTED_STATISTICS] | None = None) -> None:
        """Initialize the accumulator.

        Args:
            statistics: List of statistics to compute. If None, computes all 9.
        """
        self._statistics: list[SUPPORTED_STATISTICS] = (
            statistics if statistics is not None else ALL_STATISTICS.copy()
        )
        self._values: list[float] = []

    def add(self, values: list[float]) -> None:
        """Add values to the accumulator.

        Args:
            values: List of numeric values to add.
        """
        self._values.extend(values)

    def compute(self) -> dict[str, float]:
        """Compute and return all configured statistics.

        Returns:
            Dictionary mapping statistic names to computed values.
            Returns NaN for all statistics if no values have been added.

        Raises:
            ValueError: If an unsupported statistic is requested.
        """
        if not self._values:
            return {stat: float("nan") for stat in self._statistics}

        arr = np.array(self._values, dtype=np.float64)
        result: dict[str, float] = {}

        for stat in self._statistics:
            if stat == "mean":
                result["mean"] = float(np.mean(arr))
            elif stat == "std":
                result["std"] = float(np.std(arr, ddof=0))
            elif stat == "median":
                result["median"] = float(np.median(arr))
            elif stat == "p025":
                result["p025"] = float(np.percentile(arr, 2.5))
            elif stat == "p975":
                result["p975"] = float(np.percentile(arr, 97.5))
            elif stat == "min":
                result["min"] = float(np.min(arr))
            elif stat == "max":
                result["max"] = float(np.max(arr))
            elif stat == "count":
                result["count"] = float(len(arr))
            elif stat == "iqr":
                q_vals: npt.NDArray[np.float64] = np.percentile(arr, [75, 25])  # type: ignore[assignment]
                result["iqr"] = float(q_vals[0] - q_vals[1])

        return result
