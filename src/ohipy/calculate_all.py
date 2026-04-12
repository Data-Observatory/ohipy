#!/usr/bin/env python3
"""OHI Calculate All - Full orchestrator for OHI scores (Polars-native)."""

from __future__ import annotations

from typing import Any

import polars as pl

# Import goal index calculator
from ohipy.calculate import calculate_goal_index

# pyright: reportGeneralTypeIssues=false, reportCallIssue=false, reportArgumentType=false, reportAttributeAccessIssue=false
from ohipy.config import load_config

# Import dimension calculators
from ohipy.dimensions.pressures import calculate_pressures_all
from ohipy.dimensions.resilience import calculate_resilience_all
from ohipy.goals.ao import AO
from ohipy.goals.bd import BD
from ohipy.goals.cp import CP
from ohipy.goals.cs import CS
from ohipy.goals.cw import CW
from ohipy.goals.eco import ECO

# Import all 18 goal functions (14 pre-index + 4 post-index)
from ohipy.goals.fis import FIS
from ohipy.goals.fp import FP
from ohipy.goals.hab import HAB
from ohipy.goals.ico import ICO
from ohipy.goals.le import LE
from ohipy.goals.liv import LIV
from ohipy.goals.lsp import LSP
from ohipy.goals.mar import MAR
from ohipy.goals.np import NP
from ohipy.goals.sp import SP
from ohipy.goals.spp import SPP
from ohipy.goals.tr import TR
from ohipy.layers import load_layers

# Import postprocessing functions
from ohipy.postprocess import finalize_scores
from ohipy.types import ConfigData, LayerDict


def _as_polars_frame(value: object) -> pl.DataFrame:
    if isinstance(value, pl.DataFrame):
        return value.clone()
    if isinstance(value, pl.LazyFrame):
        return value.collect()
    try:
        return pl.DataFrame(value)
    except Exception:
        return pl.DataFrame()


def _is_not_nan(value: object) -> bool:
    return value is not None and not (isinstance(value, float) and value != value)


# Goal function registry - maps goal codes to their calculation functions
GOAL_FUNCTIONS = {
    "FIS": FIS,
    "MAR": MAR,
    "AO": AO,
    "NP": NP,
    "CS": CS,
    "CP": CP,
    "TR": TR,
    "LIV": LIV,
    "ECO": ECO,
    "ICO": ICO,
    "LSP": LSP,
    "CW": CW,
    "HAB": HAB,
    "SPP": SPP,
    "FP": FP,
    "LE": LE,
    "SP": SP,
    "BD": BD,
}


def calculate_all(
    config: ConfigData | None = None,
    layers: LayerDict | None = None,
    *,
    skip_pressures: bool = False,
    skip_resilience: bool = False,
) -> pl.DataFrame:
    """Calculate all OHI scores following R CalculateAll.R workflow.

    Args:
        config: Configuration data. Loads default if None.
        layers: Layer data dictionary. Loads default if None.
        skip_pressures: If True, skip pressure calculations and use neutral
            values (score=0.0) for all goals/regions. Useful for debugging or
            isolating status/trend contributions.
        skip_resilience: If True, skip resilience calculations and use neutral
            values (score=100.0) for all goals/regions. When combined with
            skip_pressures, the resilience cap zeroes both out, giving the
            formula xF = (1 + β·trend) · status/2.
    """
    # Load config and layers if not provided
    if config is None:
        config = load_config()
    if layers is None:
        layers = load_layers(config)

    goals_df = _as_polars_frame(config["goals"])
    config_dict = config["config"]
    constants = config_dict.get("constants", {})  # type: ignore[union-attr]
    if not isinstance(constants, dict):
        constants = {}

    # Initialize empty scores dataframe
    scores = pl.DataFrame(
        schema={
            "goal": pl.String,
            "dimension": pl.String,
            "region_id": pl.Int64,
            "score": pl.Float64,
        }
    )

    # STEP 1: Setup (optional) - skip for now
    # if 'Setup' in config.get("functions", {}):
    #     config["functions"]["Setup"]()

    # STEP 2: Pre-index functions (status/trend for 14 goals)
    preindex_goals = goals_df.filter(pl.col("preindex_function").is_not_null()).sort(
        "order_calculate"
    )

    for row in preindex_goals.iter_rows(named=True):
        goal_code = str(row["goal"])
        if row["preindex_function"] is None:
            continue

        func = GOAL_FUNCTIONS[goal_code]
        status_df_raw, trend_df_raw = func(layers)  # type: ignore[operator]
        status_df = _as_polars_frame(status_df_raw).with_columns(pl.lit(goal_code).alias("goal"))
        trend_df = _as_polars_frame(trend_df_raw).with_columns(pl.lit(goal_code).alias("goal"))

        scores = pl.concat(
            [
                scores,
                status_df.select(["goal", "dimension", "region_id", "score"]),
                trend_df.select(["goal", "dimension", "region_id", "score"]),
            ],
            how="vertical_relaxed",
        )

    # STEP 3: Pressures (all goals)
    if skip_pressures:
        status_pairs = (
            scores.filter(pl.col("dimension") == "status").select(["goal", "region_id"]).unique()
        )
        pressures_df = status_pairs.with_columns(
            [pl.lit(0.0).alias("score"), pl.lit("pressures").alias("dimension")]
        )
    else:
        pressures_df = _as_polars_frame(calculate_pressures_all(config, layers)).with_columns(
            pl.lit("pressures").alias("dimension")
        )
    scores = pl.concat(
        [scores, pressures_df.select(["goal", "dimension", "region_id", "score"])],
        how="vertical_relaxed",
    )

    # STEP 4: Resilience (all goals)
    if skip_resilience:
        status_pairs = (
            scores.filter(pl.col("dimension") == "status").select(["goal", "region_id"]).unique()
        )
        resilience_df = status_pairs.with_columns(
            [pl.lit(100.0).alias("score"), pl.lit("resilience").alias("dimension")]
        )
    else:
        resilience_df = _as_polars_frame(calculate_resilience_all(config, layers)).with_columns(
            pl.lit("resilience").alias("dimension")
        )
    scores = pl.concat(
        [scores, resilience_df.select(["goal", "dimension", "region_id", "score"])],
        how="vertical_relaxed",
    )

    # STEP 5: Goal index (future/score) for all goals with status
    goals_with_status = (
        scores.filter(pl.col("dimension") == "status").select("goal").unique().to_series().to_list()
    )

    for goal in goals_with_status:
        # Get all dimensions for this goal
        goal_scores = scores.filter(pl.col("goal") == goal).pivot(
            on="dimension", index="region_id", values="score"
        )

        if "status" not in goal_scores.columns:
            continue

        valid_regions = goal_scores.filter(pl.col("status").is_not_null())

        # Calculate goal index for each region
        index_rows_list: list[dict[str, Any]] = []
        score_rows_list: list[dict[str, Any]] = []

        has_pressures = "pressures" in goal_scores.columns
        has_resilience = "resilience" in goal_scores.columns

        for region_row in valid_regions.iter_rows(named=True):
            rid = region_row["region_id"]
            status = (
                float(region_row["status"]) / 100.0
                if _is_not_nan(region_row.get("status"))
                else None
            )
            trend = region_row.get("trend")
            pressures = (
                float(region_row["pressures"]) / 100.0
                if has_pressures and _is_not_nan(region_row.get("pressures"))
                else None
            )
            resilience = (
                float(region_row["resilience"]) / 100.0
                if has_resilience and _is_not_nan(region_row.get("resilience"))
                else None
            )

            # Apply resilience cap: r = min(r, p)
            if resilience is not None and pressures is not None:
                resilience = min(resilience, pressures)

            # Calculate goal index
            result = calculate_goal_index(
                id=rid,
                status=status,
                trend=trend,
                resilience=resilience,
                pressure=pressures,
                DISCOUNT=float(constants.get("goal_discount", 1.0)),
                BETA=float(constants.get("goal_beta", 0.67)),
                default_trend=int(constants.get("default_trend", 0)),
            )

            # Only add rows if future and score are not NaN
            if _is_not_nan(result.get("xF")) and _is_not_nan(result.get("score")):
                index_rows_list.append(
                    {
                        "region_id": rid,
                        "goal": goal,
                        "dimension": "future",
                        "score": float(result["xF"]) * 100,
                    }
                )
                score_rows_list.append(
                    {
                        "region_id": rid,
                        "goal": goal,
                        "dimension": "score",
                        "score": float(result["score"]) * 100,
                    }
                )

        # Remove old future/score rows for this goal
        scores = scores.filter(
            ~((pl.col("goal") == goal) & (pl.col("dimension").is_in(["future", "score"])))
        )

        # Add new rows
        frames = [scores]
        if index_rows_list:
            frames.append(
                pl.DataFrame(index_rows_list).select(["goal", "dimension", "region_id", "score"])
            )
        if score_rows_list:
            frames.append(
                pl.DataFrame(score_rows_list).select(["goal", "dimension", "region_id", "score"])
            )
        scores = pl.concat(frames, how="vertical_relaxed")

    # STEP 6: Post-index functions (supragoals)
    # Goals with no parent are supragoals
    supragoals = goals_df.filter(pl.col("parent").is_null())

    for row in supragoals.iter_rows(named=True):
        goal_code = str(row["goal"])
        if row["postindex_function"] is None:
            continue

        # Execute post-index function
        func = GOAL_FUNCTIONS[goal_code]

        # Handle different function signatures
        # - LE(scores, layers) returns updated scores DataFrame
        # - FP, SP, BD(layers, scores) return updated scores DataFrame
        if goal_code == "LE":
            result_raw = func(scores, layers)  # type: ignore[operator]
        else:
            result_raw = func(layers, scores)  # type: ignore[operator]

        scores = _as_polars_frame(result_raw).select(["goal", "dimension", "region_id", "score"])

    # STEP 7: Regional Index Score (weighted mean of supragoals)
    supragoal_list = supragoals.select("goal").to_series().to_list()
    supragoal_scores = scores.filter(
        pl.col("goal").is_in(supragoal_list) & (pl.col("dimension") == "score")
    )

    if supragoal_scores.height > 0:
        index_weights = supragoals.select(["goal", "weight"]).with_columns(
            pl.col("weight").cast(pl.Float64, strict=False)
        )

        # Merge with goal weights (MUST merge before filtering to preserve all weights)
        regional_index = supragoal_scores.join(index_weights, on="goal", how="left")

        regional_index = regional_index.filter(pl.col("score").is_not_null())

        if regional_index.height > 0:
            index_scores = (
                regional_index.with_columns((pl.col("score") * pl.col("weight")).alias("_weighted"))
                .group_by("region_id")
                .agg(
                    [
                        pl.col("_weighted").sum().alias("_weighted_sum"),
                        pl.col("weight").sum().alias("_weight_sum"),
                    ]
                )
                .with_columns((pl.col("_weighted_sum") / pl.col("_weight_sum")).alias("score"))
                .select(["region_id", "score"])
                .with_columns(
                    [
                        pl.lit("Index").alias("goal"),
                        pl.lit("score").alias("dimension"),
                    ]
                )
                .select(["goal", "dimension", "region_id", "score"])
            )

            # Add to scores (filter out existing Index score rows to avoid duplicates)
            scores = scores.filter(
                ~((pl.col("goal") == "Index") & (pl.col("dimension") == "score"))
            )
            scores = pl.concat([scores, index_scores], how="vertical_relaxed")

    # STEP 8: Regional Likely Future (weighted mean of supragoals)
    supragoal_futures = scores.filter(
        pl.col("goal").is_in(supragoal_list) & (pl.col("dimension") == "future")
    )

    if supragoal_futures.height > 0:
        index_weights = supragoals.select(["goal", "weight"]).with_columns(
            pl.col("weight").cast(pl.Float64, strict=False)
        )

        # Merge with goal weights (MUST merge before filtering to preserve all weights)
        regional_future = supragoal_futures.join(index_weights, on="goal", how="left")

        regional_future = regional_future.filter(pl.col("score").is_not_null())

        if regional_future.height > 0:
            future_scores = (
                regional_future.with_columns(
                    (pl.col("score") * pl.col("weight")).alias("_weighted")
                )
                .group_by("region_id")
                .agg(
                    [
                        pl.col("_weighted").sum().alias("_weighted_sum"),
                        pl.col("weight").sum().alias("_weight_sum"),
                    ]
                )
                .with_columns((pl.col("_weighted_sum") / pl.col("_weight_sum")).alias("score"))
                .select(["region_id", "score"])
                .with_columns(
                    [
                        pl.lit("Index").alias("goal"),
                        pl.lit("future").alias("dimension"),
                    ]
                )
                .select(["goal", "dimension", "region_id", "score"])
            )

            # Add to scores (filter out existing Index future rows to avoid duplicates)
            scores = scores.filter(
                ~((pl.col("goal") == "Index") & (pl.col("dimension") == "future"))
            )
            scores = pl.concat([scores, future_scores], how="vertical_relaxed")

    # STEP 9: PreGlobalScores (optional)
    pre_global_scores_fn = config.get("functions", {}).get("PreGlobalScores")  # type: ignore[union-attr]
    if pre_global_scores_fn is not None:
        scores = _as_polars_frame(pre_global_scores_fn(layers, config, scores)).select(
            ["goal", "dimension", "region_id", "score"]
        )

    # STEP 10: Global scores (region_id=0) - area-weighted
    region_areas_layer = layers["data"].get(config["config"]["layers"]["region_labels"])  # type: ignore[index, union-attr]

    if region_areas_layer is not None:
        region_areas = _as_polars_frame(region_areas_layer)
        rename_map = {}
        if "rgn_id" in region_areas.columns:
            rename_map["rgn_id"] = "region_id"
        if "area_km2" in region_areas.columns:
            rename_map["area_km2"] = "area"
        if rename_map:
            region_areas = region_areas.rename(rename_map)

        if {"region_id", "area"}.issubset(set(region_areas.columns)):
            region_areas = region_areas.select(["region_id", "area"])
            region_areas = region_areas.with_columns(pl.col("region_id").cast(pl.Int64))

            # Filter for score/status/future dimensions only
            global_scores = scores.filter(pl.col("dimension").is_in(["score", "status", "future"]))
            global_scores = global_scores.with_columns(pl.col("region_id").cast(pl.Int64))

            # Merge with areas
            global_with_areas = global_scores.join(region_areas, on="region_id", how="left")

            global_with_areas = global_with_areas.filter(pl.col("score").is_finite())

            global_scores = (
                global_with_areas.with_columns(
                    (pl.col("score") * pl.col("area")).alias("_weighted")
                )
                .group_by(["goal", "dimension"])
                .agg(
                    [
                        pl.col("_weighted").sum().alias("_weighted_sum"),
                        pl.col("area").sum().alias("_weight_sum"),
                    ]
                )
                .with_columns((pl.col("_weighted_sum") / pl.col("_weight_sum")).alias("score"))
                .select(["goal", "dimension", "score"])
                .with_columns(pl.lit(0).cast(pl.Int64).alias("region_id"))
                .select(["goal", "dimension", "region_id", "score"])
            )

            scores = scores.filter(
                ~(
                    (pl.col("dimension").is_in(["score", "status", "future"]))
                    & (pl.col("region_id") == 0)
                )
            )

            # Add global scores
            scores = pl.concat([scores, global_scores], how="vertical_relaxed")

    # STEP 11: FinalizeScores (optional)
    finalize_scores_fn = config.get("functions", {}).get("FinalizeScores")  # type: ignore[union-attr]
    if finalize_scores_fn is not None:
        scores = _as_polars_frame(finalize_scores_fn(layers, config, scores)).select(
            ["goal", "dimension", "region_id", "score"]
        )

    # Finalize scores - round to 2 decimals to match R behavior
    region_labels_layer = layers["data"].get(config["config"]["layers"]["region_labels"])  # type: ignore[index, union-attr]
    if region_labels_layer is None:
        raise ValueError("Missing region labels layer")

    region_labels = _as_polars_frame(region_labels_layer)
    goals = [str(goal) for goal in goals_df.select("goal").to_series().to_list()]
    scores = finalize_scores(scores, region_labels, goals)

    duplicates = scores.group_by(["region_id", "goal", "dimension"]).len().filter(pl.col("len") > 1)
    if duplicates.height > 0:
        raise ValueError("Duplicate (region_id, goal, dimension) combinations found")

    return scores
