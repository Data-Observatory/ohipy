#!/usr/bin/env python3
"""OHI Calculate All - Full orchestrator for OHI scores.

Follows R CalculateAll.R exact sequence to produce scores_2024_py.csv matching scores_2024_r.csv fixture.
"""

from typing import Any, cast

import numpy as np
import pandas as pd

# Import goal index calculator
from ohipy.calculate import calculate_goal_index

# suppress strict LSP typing for pandas-heavy orchestration
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


def _ensure_dataframe(value: object) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value
    return pd.DataFrame(value)


def _as_dataframe(value: object) -> pd.DataFrame:
    df = _ensure_dataframe(value)
    return cast(pd.DataFrame, df)


def calculate_all(config=None, layers=None):
    """
    Calculate all OHI scores following R CalculateAll.R workflow.

    Args:
        config: Configuration dictionary (if None, loads from config.yaml)
        layers: Layers dictionary (if None, loads from layers directory)

    Returns:
        DataFrame with columns: [goal, dimension, region_id, score]
    """
    # Load config and layers if not provided
    if config is None:
        config = load_config()
    if layers is None:
        layers = load_layers(config)

    goals_df = cast(pd.DataFrame, config["goals"])
    config_dict = cast(dict[str, Any], config["config"])
    constants = cast(dict[str, Any], config_dict.get("constants", {}))

    # Initialize empty scores dataframe
    scores = pd.DataFrame(columns=pd.Index(["goal", "dimension", "region_id", "score"]))

    # STEP 1: Setup (optional) - skip for now
    # if 'Setup' in config.get("functions", {}):
    #     config["functions"]["Setup"]()

    # STEP 2: Pre-index functions (status/trend for 14 goals)
    preindex_goals = goals_df[goals_df["preindex_function"].notna()]
    preindex_goals = preindex_goals.sort_values(by=["order_calculate"])

    for _, row in preindex_goals.iterrows():
        goal_code = str(row["goal"])
        func_code = row["preindex_function"]
        if bool(pd.notna(func_code)):
            func = GOAL_FUNCTIONS[goal_code]
            status_df_raw, trend_df_raw = func(layers)
            status_df: pd.DataFrame = _ensure_dataframe(status_df_raw).copy()
            trend_df: pd.DataFrame = _ensure_dataframe(trend_df_raw).copy()
            status_df["goal"] = goal_code
            trend_df["goal"] = goal_code
            scores = cast(
                pd.DataFrame,
                pd.concat([scores, status_df, trend_df], ignore_index=True),
            )

    # STEP 3: Pressures (all goals)
    pressures_df_raw = calculate_pressures_all(config, layers)
    pressures_df = _as_dataframe(pressures_df_raw)
    pressures_df["dimension"] = "pressures"
    scores = cast(pd.DataFrame, pd.concat([scores, pressures_df], ignore_index=True))

    # STEP 4: Resilience (all goals)
    resilience_df_raw = calculate_resilience_all(config, layers)
    resilience_df = _as_dataframe(resilience_df_raw)
    resilience_df["dimension"] = "resilience"
    scores = cast(pd.DataFrame, pd.concat([scores, resilience_df], ignore_index=True))

    # STEP 5: Goal index (future/score) for all goals with status
    scores = _as_dataframe(scores)
    goals_with_status = pd.unique(scores.loc[scores["dimension"] == "status", "goal"])

    for goal in goals_with_status:
        # Get all dimensions for this goal
        goal_scores = scores[(scores["goal"] == goal)].pivot(
            index="region_id", columns="dimension", values="score"
        )

        if "status" not in goal_scores.columns:
            continue

        # Filter to only regions with valid (non-NaN) status
        valid_regions = goal_scores[goal_scores["status"].notna()].index

        # Calculate goal index for each region
        index_rows_list = []
        score_rows_list = []

        for rid in valid_regions:
            status = goal_scores.loc[rid, "status"] / 100.0
            trend = goal_scores.loc[rid, "trend"]
            pressures = (
                goal_scores.loc[rid, "pressures"] / 100.0
                if "pressures" in goal_scores.columns
                else np.nan
            )
            resilience = (
                goal_scores.loc[rid, "resilience"] / 100.0
                if "resilience" in goal_scores.columns
                else np.nan
            )

            # Apply resilience cap: r = min(r, p)
            if not pd.isna(resilience) and not pd.isna(pressures):
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
            if pd.notna(result["xF"]) and pd.notna(result["score"]):
                index_rows_list.append(
                    {
                        "region_id": rid,
                        "goal": goal,
                        "dimension": "future",
                        "score": result["xF"] * 100,
                    }
                )

                score_rows_list.append(
                    {
                        "region_id": rid,
                        "goal": goal,
                        "dimension": "score",
                        "score": result["score"] * 100,
                    }
                )

        index_rows = pd.DataFrame(index_rows_list)
        score_rows = pd.DataFrame(score_rows_list)

        # Remove old future/score rows for this goal
        scores = scores[
            ~((scores["goal"] == goal) & (scores["dimension"].isin(["future", "score"])))
        ]

        # Add new rows
        scores = _as_dataframe(pd.concat([scores, index_rows, score_rows], ignore_index=True))

    # STEP 6: Post-index functions (supragoals)
    # Goals with no parent are supragoals
    supragoals = goals_df[goals_df["parent"].isna()]

    for _, row in supragoals.iterrows():
        goal_code = str(row["goal"])
        func_code = row["postindex_function"]
        if bool(pd.isna(func_code)):
            continue

        # Execute post-index function
        func = GOAL_FUNCTIONS[goal_code]

        # Handle different function signatures
        # - LE(scores, layers) returns updated scores DataFrame
        # - FP, SP, BD(layers, scores) return updated scores DataFrame
        if goal_code == "LE":
            result_raw = func(scores, layers)
        else:
            result_raw = func(layers, scores)

        scores = _as_dataframe(result_raw)

    # STEP 7: Regional Index Score (weighted mean of supragoals)
    supragoal_list = supragoals["goal"].tolist()
    supragoal_scores = scores[
        (scores["goal"].isin(supragoal_list)) & (scores["dimension"] == "score")
    ]

    if len(supragoal_scores) > 0:
        index_weights = supragoals[["goal", "weight"]].copy()
        index_weights["weight"] = pd.to_numeric(index_weights["weight"], errors="coerce")
        # Use weights directly from goals.csv (R CalculateAll.R lines 193-201)

        # Merge with goal weights (MUST merge before filtering to preserve all weights)
        regional_index = supragoal_scores.merge(index_weights, on="goal", how="left")

        # Filter out NaN scores to match R's weighted.mean(na.rm=TRUE)
        regional_index = regional_index[regional_index["score"].notna()]

        # Calculate weighted mean (handles NaN rows correctly after filtering)
        index_scores = (
            regional_index.groupby("region_id")
            .apply(lambda x: pd.Series({"score": np.average(x["score"], weights=x["weight"])}))
            .reset_index()
        )

        index_scores["goal"] = "Index"
        index_scores["dimension"] = "score"
        index_scores = index_scores[["region_id", "goal", "dimension", "score"]]

        # Add to scores (filter out existing Index score rows to avoid duplicates)
        scores = scores[~((scores["goal"] == "Index") & (scores["dimension"] == "score"))]
        scores = _as_dataframe(pd.concat([scores, index_scores], ignore_index=True))

    # STEP 8: Regional Likely Future (weighted mean of supragoals)
    supragoal_futures = scores[
        (scores["goal"].isin(supragoal_list)) & (scores["dimension"] == "future")
    ]

    if len(supragoal_futures) > 0:
        index_weights = supragoals[["goal", "weight"]].copy()
        index_weights["weight"] = pd.to_numeric(index_weights["weight"], errors="coerce")
        # Use weights directly from goals.csv (R CalculateAll.R lines 216-222)

        # Merge with goal weights (MUST merge before filtering to preserve all weights)
        regional_future = supragoal_futures.merge(index_weights, on="goal", how="left")

        # Filter out NaN scores to match R's weighted.mean(na.rm=TRUE)
        regional_future = regional_future[regional_future["score"].notna()]

        # Calculate weighted mean (handles NaN rows correctly after filtering)
        future_scores = (
            regional_future.groupby("region_id")
            .apply(lambda x: pd.Series({"score": np.average(x["score"], weights=x["weight"])}))
            .reset_index()
        )

        future_scores["goal"] = "Index"
        future_scores["dimension"] = "future"
        future_scores = future_scores[["region_id", "goal", "dimension", "score"]]

        # Add to scores (filter out existing Index future rows to avoid duplicates)
        scores = scores[~((scores["goal"] == "Index") & (scores["dimension"] == "future"))]
        scores = _as_dataframe(pd.concat([scores, future_scores], ignore_index=True))

    # STEP 9: PreGlobalScores (optional)
    if "PreGlobalScores" in config.get("functions", {}):
        scores = config["functions"]["PreGlobalScores"](layers, config, scores)

    # STEP 10: Global scores (region_id=0) - area-weighted
    # Load region areas
    region_areas_layer = layers["data"].get(config["config"]["layers"]["region_labels"])

    if region_areas_layer is not None:
        region_areas = region_areas_layer.copy()
        region_areas = region_areas.rename(columns={"rgn_id": "region_id", "area_km2": "area"})
        region_areas = region_areas[["region_id", "area"]]

        # Filter for score/status/future dimensions only
        global_scores = scores[scores["dimension"].isin(["score", "status", "future"])]

        # Merge with areas
        global_with_areas = global_scores.merge(region_areas, on="region_id", how="left")

        # Filter out NA scores to match R's weighted.mean(na.rm=TRUE)
        global_with_areas = global_with_areas[global_with_areas["score"].notna()]

        # Calculate area-weighted mean per goal/dimension
        global_scores = (
            global_with_areas.groupby(["goal", "dimension"])
            .apply(lambda x: pd.Series({"score": np.average(x["score"], weights=x["area"])}))
            .reset_index()
        )

        global_scores["region_id"] = 0
        global_scores = global_scores[["region_id", "goal", "dimension", "score"]]

        # Remove non-global rows for these dimensions
        scores = scores[
            ~(
                (scores["dimension"].isin(["score", "status", "future"]))
                & (scores["region_id"] == 0)
            )
        ]

        # Add global scores
        scores = _as_dataframe(pd.concat([scores, global_scores], ignore_index=True))

    # STEP 11: FinalizeScores (optional)
    if "FinalizeScores" in config.get("functions", {}):
        scores = config["functions"]["FinalizeScores"](layers, config, scores)

    # Finalize scores - round to 2 decimals to match R behavior
    region_labels = layers["data"].get(config["config"]["layers"]["region_labels"])
    goals = config["goals"]["goal"].tolist()
    scores = _as_dataframe(finalize_scores(scores, region_labels, goals))

    # Final validation
    # Ensure no duplicate (region_id, goal, dimension) combinations
    duplicates = scores.duplicated(subset=["region_id", "goal", "dimension"], keep=False)
    if duplicates.any():
        raise ValueError("Duplicate (region_id, goal, dimension) combinations found")

    return scores
