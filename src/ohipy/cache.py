"""Thread-safe layer caching module for ohipy."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


class LayerCache:
    """Thread-safe cache for loaded data layers.

    Provides in-memory caching of pandas DataFrames with thread-safe
    access using a lock mechanism.
    """

    def __init__(self) -> None:
        """Initialize empty cache with thread lock."""
        self._cache: dict[str, pd.DataFrame] = {}
        self._lock: threading.Lock = threading.Lock()

    def get(self, layer_name: str) -> pd.DataFrame | None:
        """Retrieve a cached layer by name.

        Args:
            layer_name: Name of the layer to retrieve.

        Returns:
            Cached DataFrame or None if not found.
        """
        with self._lock:
            return self._cache.get(layer_name)

    def set(self, layer_name: str, df: pd.DataFrame) -> None:
        """Store a layer in the cache.

        Args:
            layer_name: Name to store the layer under.
            df: DataFrame to cache.
        """
        with self._lock:
            self._cache[layer_name] = df

    def has(self, layer_name: str) -> bool:
        """Check if a layer exists in the cache.

        Args:
            layer_name: Name of the layer to check.

        Returns:
            True if layer is cached, False otherwise.
        """
        with self._lock:
            return layer_name in self._cache

    def clear(self) -> None:
        """Clear all cached layers."""
        with self._lock:
            self._cache.clear()


__all__ = ["LayerCache"]
