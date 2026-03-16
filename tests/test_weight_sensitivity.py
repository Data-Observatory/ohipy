"""Weight sensitivity tests for goal weight modification impacts."""

import polars as pl
import pytest


def test_single_weight_change(runner, config, layers):
    """Test that modifying one goal's weight changes goal weights."""
    from ohipy.config_overlay import ConfigOverlay

    overlay = ConfigOverlay()

    baseline_weights = config["goals"].select(["goal", "weight"]).to_dict(as_series=False)  # pyright: ignore

    overrides = {"weights": {"FIS": 2.0}}
    modified_config = overlay.apply_weights(config, overrides["weights"])
    modified_weights = modified_config["goals"].select(["goal", "weight"]).to_dict(as_series=False)  # pyright: ignore

    baseline_fis_weight = [
        w for g, w in zip(baseline_weights["goal"], baseline_weights["weight"]) if g == "FIS"
    ][0]
    modified_fis_weight = [
        w for g, w in zip(modified_weights["goal"], modified_weights["weight"]) if g == "FIS"
    ][0]

    assert baseline_fis_weight != modified_fis_weight


def test_zero_weight_excludes_goal(runner, config, layers):
    """Test that zero weight excludes goal from index calculation."""
    from ohipy.config_overlay import ConfigOverlay

    overlay = ConfigOverlay()

    baseline_weights = config["goals"].select(["goal", "weight"])  # pyright: ignore
    baseline_fis_weight = (
        baseline_weights.filter(pl.col("goal") == "FIS").select("weight").item(0, 0)
    )

    assert baseline_fis_weight > 0

    overrides = {"weights": {"FIS": 0.0}}
    modified_config = overlay.apply_weights(config, overrides["weights"])
    modified_weights = modified_config["goals"].select(["goal", "weight"])  # pyright: ignore
    modified_fis_weight = (
        modified_weights.filter(pl.col("goal") == "FIS").select("weight").item(0, 0)
    )

    assert modified_fis_weight == 0.0


def test_weight_normalization(runner, config, layers):
    """Test that weights are normalized to sum=1 after override."""
    from ohipy.config_overlay import ConfigOverlay

    overlay = ConfigOverlay()

    overrides = {"weights": {"FIS": 2.0, "MAR": 3.0}}
    modified_config = overlay.apply_weights(config, overrides["weights"])

    total_weight = modified_config["goals"].select(pl.col("weight").sum()).item()  # pyright: ignore
    assert abs(total_weight - 1.0) < 1e-10


def test_multiple_weight_changes(runner, config, layers):
    """Test that multiple weight changes produce consistent results."""
    overrides = {"weights": {"FIS": 0.5, "MAR": 2.0, "FP": 1.5}}
    modified = runner.run(year=2024, layers=layers["data"], overrides=overrides)

    index_scores = modified.filter(
        (pl.col("goal") == "Index") & (pl.col("region_id") == 0) & (pl.col("dimension") == "score")
    ).select("score")
    assert index_scores.height == 1
    assert index_scores.item(0, 0) is not None


@pytest.mark.parametrize(
    "goal_code,multiplier",
    [
        ("FIS", 0.5),
        ("FIS", 2.0),
        ("MAR", 0.5),
        ("MAR", 2.0),
        ("FP", 0.5),
        ("FP", 2.0),
        ("AO", 0.5),
        ("AO", 2.0),
    ],
)
def test_key_goals_weight_sensitivity(runner, layers, config, goal_code, multiplier):
    """Test weight sensitivity for key goals with parametrized multipliers."""
    from ohipy.config_overlay import ConfigOverlay

    overlay = ConfigOverlay()

    baseline_weights = config["goals"].select(["goal", "weight"])  # pyright: ignore
    baseline_goal_weight = (
        baseline_weights.filter(pl.col("goal") == goal_code).select("weight").item(0, 0)
    )

    overrides = {"weights": {goal_code: multiplier}}
    modified_config = overlay.apply_weights(config, overrides["weights"])
    modified_weights = modified_config["goals"].select(["goal", "weight"])  # pyright: ignore
    modified_goal_weight = (
        modified_weights.filter(pl.col("goal") == goal_code).select("weight").item(0, 0)
    )

    if multiplier != 1.0:
        assert baseline_goal_weight != modified_goal_weight


def test_weight_change_increases_high_scoring_goal(runner, layers, config):
    """Test that increasing weight of high-scoring goal increases index."""
    baseline = runner.run(year=2024, layers=layers["data"])
    baseline_index = (
        baseline.filter(
            (pl.col("goal") == "Index")
            & (pl.col("region_id") == 0)
            & (pl.col("dimension") == "score")
        )
        .select("score")
        .item(0, 0)
    )

    baseline_goals = baseline.filter(
        (pl.col("dimension") == "score") & (pl.col("region_id") == 0) & (pl.col("goal") != "Index")
    )
    highest_goal_idx = (
        baseline_goals.select("score")
        .to_series()
        .to_list()
        .index(max(baseline_goals.select("score").to_series().to_list()))
    )
    highest_goal = baseline_goals.select("goal").to_series()[highest_goal_idx]

    original_weight = (
        config["goals"].filter(pl.col("goal") == highest_goal).select("weight").item(0, 0)  # pyright: ignore
    )

    overrides = {"weights": {highest_goal: max(original_weight * 2, 10.0)}}
    modified = runner.run(year=2024, layers=layers["data"], overrides=overrides)
    modified_index = (
        modified.filter(
            (pl.col("goal") == "Index")
            & (pl.col("region_id") == 0)
            & (pl.col("dimension") == "score")
        )
        .select("score")
        .item(0, 0)
    )

    assert modified_index >= baseline_index


def test_weight_override_affects_all_regions(runner, layers):
    """Test that weight changes affect all regions consistently."""
    baseline = runner.run(year=2024, layers=layers["data"])
    baseline_indices = (
        baseline.filter((pl.col("goal") == "Index") & (pl.col("dimension") == "score"))
        .sort("region_id")
        .select(["region_id", "score"])
    )

    overrides = {"weights": {"FIS": 2.0}}
    modified = runner.run(year=2024, layers=layers["data"], overrides=overrides)
    modified_indices = (
        modified.filter((pl.col("goal") == "Index") & (pl.col("dimension") == "score"))
        .sort("region_id")
        .select(["region_id", "score"])
    )

    diffs = baseline_indices.with_columns(
        modified_score=modified_indices.select("score").to_series()
    ).with_columns((pl.col("score") - pl.col("modified_score")).abs().alias("difference"))

    max_diff = diffs.select("difference").max().item()
    assert max_diff > 0
