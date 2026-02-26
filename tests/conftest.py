"""Pytest fixtures for ohipy tests."""

import pytest

from ohipy.config import load_config
from ohipy.layers import load_layers
from ohipy.runner import OHIRunner


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
