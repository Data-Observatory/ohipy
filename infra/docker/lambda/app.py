from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any

import boto3
import polars as pl

from ohipy.pipeline import OHIPipeline


_LOCAL_DATASETS_CACHE: dict[str, str] = {}
_TRUE_STRINGS = {"1", "true", "yes", "on"}
_FALSE_STRINGS = {"0", "false", "no", "off", ""}

_SENTINEL = -999.0

_LAYER_ERRORS: list[tuple[str, str, str, bool, bool]] = [
    ("No resilience layer data found", "missing_resilience_layer", "resilience", False, True),
    ("Missing layer/dataframe:",       "missing_resilience_layer", "resilience", False, True),
    ("Missing pressures_matrix",       "missing_pressures_matrix", "pressures",  True,  False),
    ("Missing region labels layer",    "missing_region_labels",    "all",         False, False),
]


def _classify_layer_error(message: str) -> tuple[str, str, bool, bool] | None:
    for prefix, code, affected, skip_p, skip_r in _LAYER_ERRORS:
        if message.startswith(prefix):
            return code, affected, skip_p, skip_r
    return None


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE_STRINGS:
            return True
        if lowered in _FALSE_STRINGS:
            return False
    return bool(value)



def _extract_weights(goal_subgoal_weight: Any) -> dict[str, float] | None:
    if not goal_subgoal_weight:
        return None

    parsed_weights: dict[str, float] = {}

    if isinstance(goal_subgoal_weight, dict):
        items = goal_subgoal_weight.items()
    elif isinstance(goal_subgoal_weight, list):
        items: list[tuple[Any, Any]] = []
        for item in goal_subgoal_weight:
            if isinstance(item, dict):
                items.extend(item.items())
    else:
        raise ValueError("config.goalSubgoalWeight must be an object or list of objects")

    for raw_goal, raw_weight in items:
        clean = str(raw_goal).strip()
        normalized = "Index" if clean.lower() == "index" else clean.upper()
        parsed_weights[normalized] = float(raw_weight)

    return parsed_weights or None


def _flatten_disabled_columns(groups: Any, label: str) -> list[str]:
    if not groups:
        return []
    if not isinstance(groups, list):
        raise ValueError(f"config.{label} must be a list of objects")

    disabled: list[str] = []
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError(f"config.{label} entries must be objects")
        for columns in group.values():
            if not isinstance(columns, list):
                raise ValueError(f"config.{label} values must be arrays")
            for column in columns:
                col_name = str(column).strip()
                if col_name:
                    disabled.append(col_name)

    return list(dict.fromkeys(disabled))


def _download_s3_prefix(bucket: str, prefix: str, local_dir: Path) -> None:
    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    normalized_prefix = prefix.strip("/")
    key_prefix = f"{normalized_prefix}/"
    found = False

    for page in paginator.paginate(Bucket=bucket, Prefix=normalized_prefix):
        for obj in page.get("Contents", []):
            key = obj.get("Key", "")
            if key.endswith("/"):
                continue
            found = True
            relative = key[len(key_prefix) :] if key.startswith(key_prefix) else key
            if not relative:
                continue
            target = local_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, key, str(target))

    if not found:
        raise ValueError(f"No objects found in s3://{bucket}/{normalized_prefix}")


def _resolve_data_path(repeat_id: str | int | None) -> tuple[str, str]:
    bucket = (os.getenv("DATA_S3_BUCKET") or "").strip()
    if not bucket:
        return ".", "local:."

    base_prefix = (os.getenv("DATA_S3_BASE_PREFIX") or "").strip()
    if not base_prefix:
        raise ValueError("DATA_S3_BASE_PREFIX is required when DATA_S3_BUCKET is configured")

    template = (os.getenv("DATA_S3_REPEAT_PREFIX_TEMPLATE") or "").strip()
    clean_repeat_id = str(repeat_id).strip() if repeat_id is not None else None

    if clean_repeat_id is None:
        selected_prefix = base_prefix
        suffix = "base"
    elif template:
        selected_prefix = template.format(base_prefix=base_prefix, repeat_id=clean_repeat_id)
        suffix = f"repeat-{clean_repeat_id}"
    else:
        selected_prefix = f"{base_prefix.rstrip('/')}/repeat_{clean_repeat_id}"
        suffix = f"repeat-{clean_repeat_id}"

    selected_prefix = selected_prefix.strip("/")
    source_uri = f"s3://{bucket}/{selected_prefix}"
    if source_uri in _LOCAL_DATASETS_CACHE:
        return _LOCAL_DATASETS_CACHE[source_uri], source_uri

    local_dir = Path("/tmp") / "ohipy-data" / suffix
    local_dir.mkdir(parents=True, exist_ok=True)
    _download_s3_prefix(bucket=bucket, prefix=selected_prefix, local_dir=local_dir)

    _LOCAL_DATASETS_CACHE[source_uri] = str(local_dir)
    return str(local_dir), source_uri


def _apply_output_filters(
    scores: pl.DataFrame,
    region_ids: list[str] | None,
) -> pl.DataFrame:
    filtered = scores

    if region_ids:
        region_as_int: list[int] = []
        region_as_str: list[str] = []
        for rid in region_ids:
            clean = str(rid).strip()
            if not clean:
                continue
            region_as_str.append(clean)
            if clean.isdigit():
                region_as_int.append(int(clean))

        if region_as_int:
            filtered = filtered.filter(pl.col("region_id").is_in(region_as_int))
        elif region_as_str:
            filtered = filtered.filter(pl.col("region_id").cast(pl.Utf8).is_in(region_as_str))

    return filtered


def _dimension_payload(value: float) -> dict[str, Any]:
    delta = value * 0.15
    return {
        "value": value,
        "lower": value - delta,
        "upper": value + delta,
        "average": value,
        "extra": [],
        "percentage": 0.15,
    }


def _missing_payload() -> dict[str, Any]:
    return {
        "value": _SENTINEL,
        "lower": _SENTINEL,
        "upper": _SENTINEL,
        "average": _SENTINEL,
        "extra": [],
        "percentage": 0.15,
    }


def _format_scores(rows: list[dict[str, Any]], year: int) -> list[dict[str, Any]]:
    comunes: dict[int, dict[str, Any]] = {}

    for row in rows:
        raw_score = row["score"]
        if raw_score is None:
            continue
        value = float(raw_score)
        if value != value:  # NaN check
            continue
        region_id = int(row["region_id"])
        goal = str(row["goal"])
        dimension = str(row["dimension"])

        region_entry = comunes.get(region_id)
        if region_entry is None:
            region_entry = {"idRegion": region_id, "goals": {}}
            comunes[region_id] = region_entry

        goals_map: dict[str, dict[str, Any]] = region_entry["goals"]
        goal_entry = goals_map.get(goal)
        if goal_entry is None:
            goal_entry = {"name": goal, "dimension": []}
            goals_map[goal] = goal_entry

        payload = _missing_payload() if value == _SENTINEL else _dimension_payload(value)
        goal_entry["dimension"].append({"name": dimension, **payload})

    formatted_comunes: list[dict[str, Any]] = []
    for region_entry in comunes.values():
        goals_map = region_entry["goals"]
        region_entry["goals"] = list(goals_map.values())
        formatted_comunes.append(region_entry)

    return [
        {
            "year": str(year),
            "comunes": formatted_comunes,
        }
    ]


def _run_single_scenario(
    *,
    scenario: dict[str, Any],
    fallback_year: Any,
    fallback_weights: Any,
    fallback_disable: Any,
    fallback_skip_pressures: Any,
    fallback_skip_resilience: Any,
) -> dict[str, Any]:
    filters = scenario.get("filters") or {}
    config = scenario.get("config") or {}
    sensibility = config.get("sensibility") or {}

    year = int(filters.get("year", fallback_year))
    region_ids = filters.get("regionIds")
    if region_ids is not None and not isinstance(region_ids, list):
        raise ValueError("filters.regionIds must be an array")

    weights = _extract_weights(config.get("goalSubgoalWeight")) or fallback_weights

    disabled_from_pressures = _flatten_disabled_columns(config.get("pressures"), "pressures")
    disabled_from_resilience = _flatten_disabled_columns(config.get("resiliences"), "resiliences")
    disabled_from_payload = list(dict.fromkeys(disabled_from_pressures + disabled_from_resilience))

    disable = disabled_from_payload or fallback_disable
    if disable is not None and not isinstance(disable, list):
        raise ValueError("disable must be a list")

    skip_pressures = _as_bool(config.get("skipPressures"), _as_bool(fallback_skip_pressures, False))
    skip_resilience = _as_bool(config.get("skipResilience"), _as_bool(fallback_skip_resilience, False))

    repeat_id = (
        sensibility.get("repeatId")
        or sensibility.get("repeat_id")
        or scenario.get("repeatId")
        or scenario.get("repeat_id")
    )

    data_path, data_source = _resolve_data_path(repeat_id)
    pipeline = OHIPipeline(data_path=data_path)

    scenario_errors: list[dict[str, Any]] = []

    try:
        scores = pipeline.run(
            year=year,
            weights=weights,
            disable=disable,
            skip_pressures=skip_pressures,
            skip_resilience=skip_resilience,
        )
    except ValueError as exc:
        classification = _classify_layer_error(str(exc))
        if classification is None:
            raise
        code, affected, extra_skip_p, extra_skip_r = classification
        scenario_errors.append({"code": code, "detail": str(exc), "affected": affected})

        if affected == "all":
            scores = pl.DataFrame(
                schema={"goal": pl.String, "dimension": pl.String, "region_id": pl.Int64, "score": pl.Float64}
            )
        else:
            scores = pipeline.run(
                year=year,
                weights=weights,
                disable=disable,
                skip_pressures=skip_pressures or extra_skip_p,
                skip_resilience=skip_resilience or extra_skip_r,
            )
            sentinel_dims = ["score"]
            scores = scores.with_columns(
                pl.when(pl.col("dimension").is_in(sentinel_dims))
                .then(pl.lit(_SENTINEL))
                .otherwise(pl.col("score"))
                .alias("score")
            )

    filtered_scores = _apply_output_filters(
        scores=scores,
        region_ids=region_ids,
    )

    rows = (
        filtered_scores.filter(pl.col("score").is_not_null())
        .select(["goal", "dimension", "region_id", "score"])
        .to_dicts()
    )
    formatted_scores = _format_scores(rows, year)

    return {
        "year": year,
        "repeat_id": repeat_id,
        "data_source": data_source,
        "disabled": {
            "pressures": disabled_from_pressures,
            "resiliences": disabled_from_resilience,
            "all": disabled_from_payload,
        },
        "row_count": len(rows),
        "scores": formatted_scores,
        "errors": scenario_errors,
    }


def _parse_event_body(event: dict[str, Any]) -> dict[str, Any]:
    
    raw_body = event.get("body")
    if raw_body in (None, ""):
        return {}

    if not isinstance(raw_body, str):
        raise ValueError("Request body must be a JSON string")

    return json.loads(raw_body)


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    started = time.perf_counter()

    try:
        body = _parse_event_body(event)
        legacy_year = body.get("year")
        scenarios = body.get("scenarios")

        if scenarios is None:
            scenarios = [{}]
        elif not isinstance(scenarios, list):
            raise ValueError("scenarios must be an array")

        results: list[dict[str, Any]] = []
        for index, scenario in enumerate(scenarios):
            if not isinstance(scenario, dict):
                raise ValueError("Each scenario must be an object")
            scenario_result = _run_single_scenario(
                scenario=scenario,
                fallback_year=legacy_year,
                fallback_weights=body.get("weights"),
                fallback_disable=body.get("disable"),
                fallback_skip_pressures=body.get("skip_pressures"),
                fallback_skip_resilience=body.get("skip_resilience"),
            )
            scenario_result["scenario_index"] = index
            results.append(scenario_result)

        elapsed_ms = int((time.perf_counter() - started) * 1000)

        all_errors = [err for r in results for err in r.get("errors", [])]
        status_field: dict[str, Any] = {"ok": len(all_errors) == 0, "errors": all_errors}
        status_code = 201 if all_errors else 200

        response_body: dict[str, Any] = {
            "scenario_count": len(results),
            "status": status_field,
            "scenarios": results,
        }

        if body.get("title"):
            response_body["title"] = body["title"]
        if body.get("description"):
            response_body["description"] = body["description"]

        if body.get("scenarios") is None and len(results) == 1:
            single = results[0]
            response_body = {
                "status": status_field,
                "year": single["year"],
                "repeat_id": single.get("repeat_id"),
                "data_source": single.get("data_source"),
                "disabled": single.get("disabled"),
                "row_count": single["row_count"],
                "scores": single["scores"],
            }

        return _response(status_code, response_body)
    except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return _response(400, {"error": "invalid_request", "detail": str(exc)})
    except Exception as exc: 
        return _response(500, {"error": "internal_error", "detail": str(exc)})
