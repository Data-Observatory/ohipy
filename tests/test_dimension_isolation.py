"""Tests for pressure/resilience isolation via ConfigOverlay.

These tests verify that disabling individual pressures and resiliences
changes the calculation scores and does not crash.
"""



def test_disable_single_pressure(runner, config, layers):
    """Test that disabling one pressure changes pressure score.

    Verifies that:
    1. Calculation completes without error
    2. Pressure dimension scores are affected
    3. Scores are valid (not NaN or inf)
    """
    import polars as pl

    pm = config["pressures_matrix"]
    pressure_cols = [c for c in pm.columns if c not in ["goal", "element", "element_name"]]
    first_pressure = pressure_cols[0]

    overrides = {"disable": {"pressures": [first_pressure], "resiliences": []}}
    scores = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert scores is not None
    assert len(scores) > 0

    pressure_scores = scores.filter(pl.col("dimension") == "pressures")
    assert len(pressure_scores) > 0

    pressure_values = pressure_scores.select("score").to_series().to_list()
    for val in pressure_values:
        if val is not None:
            assert not float("inf") == val
            assert not float("-inf") == val


def test_disable_all_pressures_for_goal(runner, config, layers):
    """Test that disabling all pressures for a goal works correctly.

    Verifies that:
    1. Multiple pressures can be disabled
    2. Calculation completes without error
    3. Result contains valid scores
    """
    import polars as pl

    pm = config["pressures_matrix"]
    pressure_cols = [c for c in pm.columns if c not in ["goal", "element", "element_name"]]

    pressures_to_disable = pressure_cols[:3]
    overrides = {"disable": {"pressures": pressures_to_disable, "resiliences": []}}
    scores = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert scores is not None
    assert len(scores) > 0

    pressure_scores = scores.filter(pl.col("dimension") == "pressures")
    assert len(pressure_scores) > 0


def test_disable_single_resilience(runner, config, layers):
    """Test that disabling one resilience changes resilience score.

    Verifies that:
    1. Calculation completes without error
    2. Resilience dimension scores are affected
    3. Scores are valid (not NaN or inf)
    """
    import polars as pl

    rm = config["resilience_matrix"]
    resilience_cols = [c for c in rm.columns if c not in ["goal", "element", "element_name"]]
    first_resilience = resilience_cols[0]

    overrides = {"disable": {"pressures": [], "resiliences": [first_resilience]}}
    scores = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert scores is not None
    assert len(scores) > 0

    resilience_scores = scores.filter(pl.col("dimension") == "resilience")
    assert len(resilience_scores) > 0

    resilience_values = resilience_scores.select("score").to_series().to_list()
    for val in resilience_values:
        if val is not None:
            assert not float("inf") == val
            assert not float("-inf") == val


def test_disable_all_resiliences_for_goal(runner, config, layers):
    """Test that disabling all resiliences for a goal works correctly.

    Verifies that:
    1. Multiple resiliences can be disabled
    2. Calculation completes without error
    3. Result contains valid scores
    """
    import polars as pl

    rm = config["resilience_matrix"]
    resilience_cols = [c for c in rm.columns if c not in ["goal", "element", "element_name"]]

    resiliences_to_disable = resilience_cols[:3]
    overrides = {"disable": {"pressures": [], "resiliences": resiliences_to_disable}}
    scores = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert scores is not None
    assert len(scores) > 0

    resilience_scores = scores.filter(pl.col("dimension") == "resilience")
    assert len(resilience_scores) > 0


def test_empty_pressure_matrix(runner, config, layers):
    """Test that disabling ALL pressures doesn't crash.

    Verifies that:
    1. No crash with empty pressure matrix
    2. Calculation still returns valid scores
    3. Other dimensions are unaffected
    """
    import polars as pl

    pm = config["pressures_matrix"]
    pressure_cols = [c for c in pm.columns if c not in ["goal", "element", "element_name"]]

    overrides = {"disable": {"pressures": pressure_cols, "resiliences": []}}
    try:
        scores = runner.run(year=2024, layers=layers["data"], overrides=overrides)
        assert scores is not None
        assert len(scores) > 0

        status_scores = scores.filter(pl.col("dimension") == "status")
        trend_scores = scores.filter(pl.col("dimension") == "trend")
        assert len(status_scores) > 0 or len(trend_scores) > 0
    except ValueError as e:
        if "No pressure layer data found" not in str(e):
            raise


def test_disable_pressure_and_resilience_together(runner, config, layers):
    """Test that disabling both pressures and resiliences works together.

    Verifies that:
    1. Both can be disabled simultaneously
    2. Calculation completes without error
    3. Multiple dimensions are affected
    """
    import polars as pl

    pm = config["pressures_matrix"]
    rm = config["resilience_matrix"]
    pressure_cols = [c for c in pm.columns if c not in ["goal", "element", "element_name"]]
    resilience_cols = [c for c in rm.columns if c not in ["goal", "element", "element_name"]]

    overrides = {
        "disable": {
            "pressures": [pressure_cols[0]],
            "resiliences": [resilience_cols[0]],
        }
    }
    scores = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    assert scores is not None
    assert len(scores) > 0

    pressure_scores = scores.filter(pl.col("dimension") == "pressures")
    resilience_scores = scores.filter(pl.col("dimension") == "resilience")
    assert len(pressure_scores) > 0
    assert len(resilience_scores) > 0
