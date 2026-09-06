"""Bounded declarative fan mappings; no executable expressions."""

from __future__ import annotations

import copy
import math
from typing import Any

RAW_TYPES = {"string", "integer", "boolean"}


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def coerce_fan_raw(value: Any, raw_type: str) -> Any:
    """Coerce a Tuya value the same way the supported source DP types do."""
    if raw_type == "string":
        if value is None:
            raise ValueError("null is not a writable string fan value")
        return str(value)
    if raw_type == "integer":
        if isinstance(value, bool):
            raise ValueError("boolean is not an integer fan value")
        try:
            result = int(value)
        except (TypeError, ValueError, OverflowError) as err:
            raise ValueError("invalid integer fan value") from err
        if isinstance(value, float) and result != value:
            raise ValueError("non-integral fan value")
        return result
    if raw_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError("invalid boolean fan value")
        return value
    raise ValueError("unsupported fan raw type")


def _raw_key(value: Any, raw_type: str) -> tuple[str, Any]:
    try:
        return raw_type, coerce_fan_raw(value, raw_type)
    except ValueError:
        return raw_type, object()


def validate_fan_speed_mapping(value: Any) -> dict[str, Any] | None:
    """Validate exact enumerated fan speed percentages."""
    if (
        not isinstance(value, dict)
        or set(value) != {"raw_type", "rules"}
        or value.get("raw_type") not in {"string", "integer"}
    ):
        return None
    rules = value.get("rules")
    if not isinstance(rules, list) or not 2 <= len(rules) <= 64:
        return None
    raw_type = value["raw_type"]
    seen_raw: set[tuple[str, Any]] = set()
    normalized: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {"dps_val", "value"}:
            return None
        if not _number(rule["value"]) or not 1 <= float(rule["value"]) <= 100:
            return None
        try:
            raw = coerce_fan_raw(rule["dps_val"], raw_type)
        except ValueError:
            return None
        key = (raw_type, raw)
        if key in seen_raw:
            return None
        seen_raw.add(key)
        percentage = float(rule["value"])
        if percentage.is_integer():
            percentage = int(percentage)
        normalized.append({"dps_val": raw, "value": percentage})
    return {"raw_type": raw_type, "rules": normalized}


def fan_speed_from_raw(raw: Any, mapping: dict[str, Any]) -> int | float | None:
    """Return the exact configured HA percentage for a raw Tuya speed."""
    raw_type = mapping["raw_type"]
    try:
        raw = coerce_fan_raw(raw, raw_type)
    except ValueError:
        return None
    for rule in mapping["rules"]:
        if rule["dps_val"] == raw:
            return rule["value"]
    return None


def fan_speed_to_raw(percentage: int | float, mapping: dict[str, Any]) -> Any:
    """Snap to the nearest configured percentage, preserving source order on ties."""
    if not _number(percentage):
        raise ValueError("invalid fan percentage")
    rule = min(mapping["rules"], key=lambda item: abs(float(item["value"]) - float(percentage)))
    return rule["dps_val"]


def validate_fan_oscillation_mapping(value: Any) -> dict[str, Any] | None:
    """Validate ordered exact/default boolean oscillation mappings."""
    if (
        not isinstance(value, dict)
        or set(value) != {"raw_type", "rules"}
        or value.get("raw_type") not in RAW_TYPES
    ):
        return None
    rules = value.get("rules")
    if not isinstance(rules, list) or not 2 <= len(rules) <= 32:
        return None
    raw_type = value["raw_type"]
    exact_values: set[bool] = set()
    seen_raw: set[tuple[str, Any]] = set()
    default_seen = False
    normalized: list[dict[str, Any]] = []
    for rule in rules:
        if (
            not isinstance(rule, dict)
            or set(rule) - {"dps_val", "value"}
            or set(rule) == set()
            or "value" not in rule
            or not isinstance(rule["value"], bool)
        ):
            return None
        item = {"value": rule["value"]}
        if "dps_val" in rule:
            try:
                raw = coerce_fan_raw(rule["dps_val"], raw_type)
            except ValueError:
                return None
            key = (raw_type, raw)
            if key in seen_raw:
                return None
            seen_raw.add(key)
            exact_values.add(rule["value"])
            item["dps_val"] = raw
        else:
            if default_seen:
                return None
            default_seen = True
        normalized.append(item)
    if exact_values != {False, True}:
        return None
    return {"raw_type": raw_type, "rules": normalized}


def fan_oscillation_from_raw(raw: Any, mapping: dict[str, Any]) -> bool | None:
    """Apply first exact rule, then the single optional fallback."""
    raw_type = mapping["raw_type"]
    try:
        coerced = coerce_fan_raw(raw, raw_type)
    except ValueError:
        coerced = object()
    fallback = None
    for rule in mapping["rules"]:
        if "dps_val" not in rule:
            fallback = rule["value"]
        elif rule["dps_val"] == coerced:
            return rule["value"]
    return fallback


def fan_oscillation_to_raw(oscillating: bool, mapping: dict[str, Any]) -> Any:
    """Use the first exact writable rule for the requested boolean state."""
    if not isinstance(oscillating, bool):
        raise ValueError("invalid oscillation state")
    for rule in mapping["rules"]:
        if "dps_val" in rule and rule["value"] is oscillating:
            return rule["dps_val"]
    raise ValueError("oscillation state has no writable rule")
