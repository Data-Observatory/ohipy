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


def _normalize_goal_name(goal_name: str) -> str:
    clean = goal_name.strip()
    if clean.lower() == "index":
        return "Index"
    return clean.upper()


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
        parsed_weights[_normalize_goal_name(str(raw_goal))] = float(raw_weight)

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
    goal_subgoal: str | None,
    dimension: str | None,
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

    if goal_subgoal:
        normalized_goal = _normalize_goal_name(goal_subgoal)
        filtered = filtered.filter(pl.col("goal") == normalized_goal)

    if dimension:
        filtered = filtered.filter(pl.col("dimension") == str(dimension).strip().lower())

    return filtered


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
    goal_subgoal = filters.get("goalSubgoal")
    dimension = filters.get("dimension")

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

    scores = pipeline.run(
        year=year,
        weights=weights,
        disable=disable,
        skip_pressures=skip_pressures,
        skip_resilience=skip_resilience,
    )

    filtered_scores = _apply_output_filters(
        scores=scores,
        region_ids=region_ids,
        goal_subgoal=goal_subgoal,
        dimension=dimension,
    )

    rows = filtered_scores.select(["goal", "dimension", "region_id", "score"]).to_dicts()

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
        "scores": rows,
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

        response_body: dict[str, Any] = {
            "scenario_count": len(results),
            "scenarios": results,
        }
        
        if body.get("title"):
            response_body["title"] = body["title"]
        if body.get("description"):
            response_body["description"] = body["description"]

        if body.get("scenarios") is None and len(results) == 1:
            single = results[0]
            response_body = {
                "year": single["year"],
                "repeat_id": single.get("repeat_id"),
                "data_source": single.get("data_source"),
                "disabled": single.get("disabled"),
                "row_count": single["row_count"],
                "scores": single["scores"],
            }

        return _response(200, response_body)
    except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return _response(400, {"error": "invalid_request", "detail": str(exc)})
    except Exception as exc: 
        return _response(500, {"error": "internal_error", "detail": str(exc)})
