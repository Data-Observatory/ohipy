"""Pytest fixtures for ohipy tests."""

from pathlib import Path

import polars as pl
import pytest

from ohipy.config import load_config
from ohipy.layers import load_layers
from ohipy.runner import OHIRunner


def pytest_configure(config):
    config.addinivalue_line("markers", "integrity: Fast data integrity tests (no Docker)")
    config.addinivalue_line("markers", "parity: Baseline R-vs-Python parity tests")
    config.addinivalue_line(
        "markers", "parity_full: Comprehensive 44-variation parity tests (Docker required)"
    )


@pytest.fixture
def config():
    """Load default OHI configuration."""
    return load_config()


@pytest.fixture
def layers(config):
    """Load default OHI layers."""
    return load_layers(config)


@pytest.fixture
def runner():
    """Create OHIRunner instance."""
    return OHIRunner()


@pytest.fixture
def fixture_config():
    return load_config(Path(__file__).parent / "fixtures" / "config.yaml")


@pytest.fixture
def fixture_layers(fixture_config):
    return load_layers(fixture_config)


@pytest.fixture
def strict_layers(config):
    """Load layers with hard-fail on missing declared layers."""
    layers_data = load_layers(config)
    layers_meta = layers_data["meta"]

    declared = layers_meta.filter(pl.col("filename").is_not_null())

    missing = []
    empty = []
    for row in declared.iter_rows(named=True):
        layer_name = row["layer"]
        if layer_name not in layers_data["data"]:
            missing.append(layer_name)
        elif len(layers_data["data"][layer_name]) == 0:
            empty.append(layer_name)

    if missing or empty:
        parts = []
        if missing:
            parts.append(f"Missing layers ({len(missing)}): {', '.join(missing[:20])}")
        if empty:
            parts.append(f"Empty layers ({len(empty)}): {', '.join(empty[:20])}")
        pytest.fail("Layer integrity check failed:\n" + "\n".join(parts))

    return layers_data
