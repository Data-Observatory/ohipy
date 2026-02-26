"""Override precedence tests for ConfigOverlay."""

import pandas as pd
import pytest


def test_disable_overrides_matrix(config):
    """Test that disable takes precedence over matrices override."""
    from ohipy.config_overlay import ConfigOverlay

    overlay = ConfigOverlay()

    # Create custom matrix with the column we want to disable
    custom_matrix = config["pressures_matrix"].copy()

    overrides = {
        "disable": {"pressures": ["pres_n_explora"], "resiliences": []},
        "matrices": {"pressures": custom_matrix},
    }

    modified = overlay.apply_all(config, overrides)

    # disable should take precedence - column should be removed
    assert "pres_n_explora" not in modified["pressures_matrix"].columns


def test_weights_independent(config):
    """Test that weights override doesn't affect P/R matrices."""
    from ohipy.config_overlay import ConfigOverlay

    overlay = ConfigOverlay()

    original_pm = config["pressures_matrix"].copy()
    original_rm = config["resilience_matrix"].copy()

    overrides = {"weights": {"FIS": 0.8, "MAR": 0.2}}

    modified = overlay.apply_all(config, overrides)

    # P/R matrices should be unchanged
    pd.testing.assert_frame_equal(modified["pressures_matrix"], original_pm)
    pd.testing.assert_frame_equal(modified["resilience_matrix"], original_rm)


def test_all_overrides_combined(config):
    """Test that all overrides work together."""
    from ohipy.config_overlay import ConfigOverlay

    overlay = ConfigOverlay()

    custom_matrix = config["pressures_matrix"].copy()

    overrides = {
        "weights": {"FIS": 0.8, "MAR": 0.2},
        "disable": {"pressures": ["pres_n_explora"], "resiliences": []},
        "matrices": {"pressures": custom_matrix},
    }

    modified = overlay.apply_all(config, overrides)

    # All effects should be applied
    assert "pres_n_explora" not in modified["pressures_matrix"].columns
    # Weights should be updated (check FIS weight changed)
    fis_weight = modified["goals"].loc[modified["goals"]["goal"] == "FIS", "weight"].iloc[0]
    assert fis_weight != config["goals"].loc[config["goals"]["goal"] == "FIS", "weight"].iloc[0]
