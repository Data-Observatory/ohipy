"""Override precedence tests for ConfigOverlay."""

import polars as pl


def test_disable_overrides_matrix(config):
    """Test that disable takes precedence over matrices override."""
    from ohipy.config_overlay import ConfigOverlay

    overlay = ConfigOverlay()

    # Create custom matrix with the column we want to disable
    custom_matrix = config["pressures_matrix"].clone()

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

    original_pm = config["pressures_matrix"].clone()
    original_rm = config["resilience_matrix"].clone()

    overrides = {"weights": {"FIS": 0.8, "MAR": 0.2}}

    modified = overlay.apply_all(config, overrides)

    assert modified["pressures_matrix"].equals(original_pm)
    assert modified["resilience_matrix"].equals(original_rm)


def test_all_overrides_combined(config):
    """Test that all overrides work together."""
    from ohipy.config_overlay import ConfigOverlay

    overlay = ConfigOverlay()

    custom_matrix = config["pressures_matrix"].clone()

    overrides = {
        "weights": {"FIS": 0.8, "MAR": 0.2},
        "disable": {"pressures": ["pres_n_explora"], "resiliences": []},
        "matrices": {"pressures": custom_matrix},
    }

    modified = overlay.apply_all(config, overrides)

    # All effects should be applied
    assert "pres_n_explora" not in modified["pressures_matrix"].columns
    # Weights should be updated (check FIS weight changed)
    fis_weight_modified = modified["goals"].filter(pl.col("goal") == "FIS").select("weight").item()
    fis_weight_original = config["goals"].filter(pl.col("goal") == "FIS").select("weight").item()
    assert fis_weight_modified != fis_weight_original
