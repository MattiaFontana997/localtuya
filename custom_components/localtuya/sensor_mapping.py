"""Bounded, read-only Tuya sensor mappings; no executable expressions."""

import copy
import math


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _scalar(value):
    return value is None or isinstance(value, (str, bool)) or _number(value)


def _range(value):
    return (isinstance(value, dict) and set(value) == {"min", "max"}
            and all(_number(v) for v in value.values()) and value["min"] < value["max"])


def validate_sensor_value_mapping(value):
    """Reject unknown grammar and non-finite or unbounded input."""
    if not isinstance(value, dict) or set(value) - {"raw_type", "rules", "range"}:
        return None
    if value.get("raw_type") not in {"string", "integer", "float", "boolean"}:
        return None
    if "range" in value and not _range(value["range"]):
        return None
    rules = value.get("rules")
    if not isinstance(rules, list) or not rules or len(rules) > 64:
        return None
    for rule in rules:
        if not isinstance(rule, dict) or not rule or set(rule) - {"dps_val", "value", "scale", "invert", "target_range", "icon"}:
            return None
        if any(not _scalar(rule[k]) for k in ("dps_val", "value") if k in rule):
            return None
        if "scale" in rule and (not _number(rule["scale"]) or rule["scale"] <= 0):
            return None
        if "invert" in rule and not isinstance(rule["invert"], bool):
            return None
        if rule.get("invert") and "range" not in value:
            return None
        if "target_range" in rule and (not _range(rule["target_range"]) or "range" not in value):
            return None
        if "icon" in rule and (not isinstance(rule["icon"], str) or not rule["icon"].startswith("mdi:")):
            return None
    return copy.deepcopy(value)


def _find_rule(raw, mapping):
    fallback = None
    for rule in mapping["rules"]:
        if "dps_val" not in rule:
            fallback = rule
        elif str(rule["dps_val"]) == str(raw):
            return rule
    return fallback


def evaluate_sensor_value_mapping(raw, mapping):
    """Match raw strings exactly; invert, project, then divide as upstream does."""
    # Upstream chooses scale and icon from the device's original value, before
    # coercing numeric strings for value-rule matching.
    original_rule = _find_rule(raw, mapping) or {}
    raw_type = mapping["raw_type"]
    if isinstance(raw, str) and raw_type != "string":
        try:
            raw = {"integer": int, "float": float, "boolean": bool}[raw_type](raw)
        except (TypeError, ValueError, OverflowError):
            pass
    selected = _find_rule(raw, mapping)
    if selected is None:
        return raw, None
    result = selected.get("value", raw)
    # bool is a Number in Tuya Local's transform path as well.
    if isinstance(result, (int, float)):
        source = mapping.get("range")
        if selected.get("invert"):
            result = source["min"] + source["max"] - result
        target = selected.get("target_range")
        if target:
            result = target["min"] + ((result - source["min"]) * (target["max"] - target["min"]) / (source["max"] - source["min"]))
        if original_rule.get("scale", 1) != 1:
            result = result / original_rule["scale"]
    return result, original_rule.get("icon")
