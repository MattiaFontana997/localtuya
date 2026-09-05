"""Safe catalog-driven value mapping for LocalTuya datapoints."""

from __future__ import annotations

from numbers import Number
from typing import Any

CONF_ADVANCED_MAPPING = "advanced_mapping"
_MAX_RULES = 64
_MAX_CONDITIONS = 16
_RULE_KEYS = {"dps_val", "value", "scale", "invert", "step", "range", "target_range", "constraint_dp", "conditions", "value_redirect_dp", "hidden", "invalid", "default"}
_CONDITION_KEYS = {"dps_val", "value", "scale", "invert", "step", "range", "target_range", "value_redirect_dp", "hidden", "invalid"}


def _valid_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def _normalize_dp(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        dp_id = int(value)
    except (TypeError, ValueError):
        return None
    return dp_id if 0 < dp_id <= 65535 else None


def _normalize_range(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict) or set(value) != {"min", "max"}:
        return None
    minimum, maximum = value.get("min"), value.get("max")
    if not isinstance(minimum, Number) or isinstance(minimum, bool) or not isinstance(maximum, Number) or isinstance(maximum, bool) or float(minimum) >= float(maximum):
        return None
    return {"min": float(minimum), "max": float(maximum)}


def _normalize_rule(raw: Any, *, condition: bool = False) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    if set(raw) - (_CONDITION_KEYS if condition else _RULE_KEYS):
        return None
    result: dict[str, Any] = {}
    for key in ("dps_val", "value"):
        if key in raw:
            value = raw[key]
            if key == "dps_val" and condition and isinstance(value, list):
                if not value or len(value) > 32 or not all(_valid_scalar(item) for item in value):
                    return None
                result[key] = list(value)
            elif not _valid_scalar(value):
                return None
            else:
                result[key] = value
    for key in ("scale", "step"):
        if key in raw:
            value = raw[key]
            if not isinstance(value, Number) or isinstance(value, bool) or float(value) <= 0:
                return None
            result[key] = float(value)
    for key in ("invert", "hidden", "invalid", "default"):
        if key in raw:
            if not isinstance(raw[key], bool):
                return None
            result[key] = raw[key]
    for key in ("range", "target_range"):
        if key in raw:
            normalized = _normalize_range(raw[key])
            if normalized is None:
                return None
            result[key] = normalized
    for key in ("constraint_dp", "value_redirect_dp"):
        if key in raw:
            dp_id = _normalize_dp(raw[key])
            if dp_id is None:
                return None
            result[key] = dp_id
    if "conditions" in raw:
        conditions = raw["conditions"]
        if condition or not isinstance(conditions, list) or len(conditions) > _MAX_CONDITIONS:
            return None
        normalized_conditions = []
        for item in conditions:
            normalized = _normalize_rule(item, condition=True)
            if normalized is None or "dps_val" not in normalized:
                return None
            normalized_conditions.append(normalized)
        result["conditions"] = normalized_conditions
    return result


def validate_advanced_mapping(value: Any) -> list[dict[str, Any]] | None:
    """Validate one declarative, non-executable mapping rule list."""
    if not isinstance(value, list) or not value or len(value) > _MAX_RULES:
        return None
    result = []
    for raw in value:
        rule = _normalize_rule(raw)
        if rule is None:
            return None
        result.append(rule)
    return result


def advanced_mapping_dp_references(value: Any) -> set[int]:
    rules = validate_advanced_mapping(value)
    if rules is None:
        return set()
    result: set[int] = set()
    for rule in rules:
        for key in ("constraint_dp", "value_redirect_dp"):
            if key in rule:
                result.add(int(rule[key]))
        for condition in rule.get("conditions", []):
            if "value_redirect_dp" in condition:
                result.add(int(condition["value_redirect_dp"]))
    return result


def prune_advanced_mapping(value: Any, optional_dps: set[int], available_dps: set[int]) -> list[dict[str, Any]] | None:
    rules = validate_advanced_mapping(value)
    if rules is None:
        return None
    result = []
    for rule in rules:
        references = {int(rule[key]) for key in ("constraint_dp", "value_redirect_dp") if key in rule}
        conditions = []
        for condition in rule.get("conditions", []):
            refs = {int(condition["value_redirect_dp"])} if "value_redirect_dp" in condition else set()
            if any(dp in optional_dps and dp not in available_dps for dp in refs):
                continue
            conditions.append(condition)
        if "conditions" in rule:
            rule = dict(rule)
            rule["conditions"] = conditions
        if any(dp in optional_dps and dp not in available_dps for dp in references):
            continue
        result.append(rule)
    return result or None


def _matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, list):
        return any(_matches(item, actual) for item in expected)
    return expected == actual or str(expected) == str(actual)


def _active_condition(rule: dict[str, Any], status: dict[str, Any]) -> dict[str, Any] | None:
    constraint_dp = rule.get("constraint_dp")
    if constraint_dp is None:
        return None
    current = status.get(str(constraint_dp))
    for condition in rule.get("conditions", []):
        if _matches(condition.get("dps_val"), current):
            return condition
    return None


def _find_rule_for_raw(rules: list[dict[str, Any]], raw: Any) -> dict[str, Any] | None:
    default = None
    for rule in rules:
        if "dps_val" not in rule:
            default = rule
        elif _matches(rule["dps_val"], raw):
            return rule
    return default


def _find_rule_for_value(rules: list[dict[str, Any]], value: Any) -> dict[str, Any] | None:
    default = None
    nearest = None
    nearest_distance = float("inf")
    for rule in rules:
        if rule.get("hidden", False):
            continue
        if "dps_val" not in rule:
            default = rule
            continue
        if "value" in rule and _matches(rule["value"], value):
            return rule
        if isinstance(rule.get("value"), Number) and isinstance(value, Number):
            distance = abs(float(rule["value"]) - float(value))
            if distance < nearest_distance:
                nearest, nearest_distance = rule, distance
        for condition in rule.get("conditions", []):
            if not condition.get("hidden", False) and "value" in condition and _matches(condition["value"], value):
                return rule
    return nearest or default


def _transform_numeric(value: Any, rule: dict[str, Any], *, reverse: bool) -> Any:
    if not isinstance(value, Number) or isinstance(value, bool):
        return value
    result = float(value)
    source_range = rule.get("range")
    target_range = rule.get("target_range")
    if reverse:
        if target_range and source_range:
            result = source_range["min"] + ((result - target_range["min"]) * (source_range["max"] - source_range["min"]) / (target_range["max"] - target_range["min"]))
        if "scale" in rule:
            result *= float(rule["scale"])
        if rule.get("invert") and source_range:
            result = source_range["min"] + source_range["max"] - result
        if "step" in rule:
            step = float(rule["step"])
            result = step * round(result / step)
    else:
        if rule.get("invert") and source_range:
            result = source_range["min"] + source_range["max"] - result
        if "scale" in rule:
            result /= float(rule["scale"])
        if target_range and source_range:
            result = target_range["min"] + ((result - source_range["min"]) * (target_range["max"] - target_range["min"]) / (source_range["max"] - source_range["min"]))
    return int(result) if result.is_integer() else result


def map_value_from_dps(raw: Any, rules: list[dict[str, Any]], status: dict[str, Any]) -> tuple[Any, int | None]:
    rule = _find_rule_for_raw(rules, raw)
    if rule is None:
        return raw, None
    active = _active_condition(rule, status)
    if active and active.get("invalid", False):
        return None, None
    effective = dict(rule)
    if active:
        effective.update({key: value for key, value in active.items() if key != "dps_val"})
    value = _transform_numeric(effective.get("value", raw), effective, reverse=False)
    return value, effective.get("value_redirect_dp")


def map_value_to_dps(value: Any, rules: list[dict[str, Any]], status: dict[str, Any], primary_dp: int) -> dict[int, Any]:
    rule = _find_rule_for_value(rules, value)
    if rule is None:
        return {primary_dp: value}
    active = _active_condition(rule, status)
    effective = dict(rule)
    if active:
        effective.update({key: item for key, item in active.items() if key != "dps_val"})
    if effective.get("invalid", False):
        raise ValueError("Value is invalid for the active advanced mapping")
    result = _transform_numeric(effective.get("dps_val", value), effective, reverse=True)
    target_dp = int(effective.get("value_redirect_dp", primary_dp))
    writes = {target_dp: result}
    constraint_dp = rule.get("constraint_dp")
    if constraint_dp is not None:
        for condition in rule.get("conditions", []):
            if "value" in condition and _matches(condition["value"], value):
                expected = condition.get("dps_val")
                if not isinstance(expected, list) and expected is not None:
                    writes[int(constraint_dp)] = expected
                break
    return writes
