"""Tests for bounded catalog fan mappings."""

from custom_components.localtuya.fan_mapping import (
    fan_oscillation_from_raw,
    fan_oscillation_to_raw,
    fan_speed_from_raw,
    fan_speed_to_raw,
    validate_fan_oscillation_mapping,
    validate_fan_speed_mapping,
)


def test_exact_custom_speed_percentages_and_closest_write():
    mapping = validate_fan_speed_mapping({
        "raw_type": "string",
        "rules": [
            {"dps_val": "1", "value": 13},
            {"dps_val": "2", "value": 25},
            {"dps_val": "3", "value": 37},
            {"dps_val": "4", "value": 50},
        ],
    })
    assert mapping is not None
    assert fan_speed_from_raw("3", mapping) == 37
    assert fan_speed_to_raw(34, mapping) == "3"
    assert fan_speed_to_raw(31, mapping) == "2"


def test_speed_tie_preserves_source_order():
    mapping = validate_fan_speed_mapping({
        "raw_type": "string",
        "rules": [
            {"dps_val": "low", "value": 25},
            {"dps_val": "high", "value": 75},
        ],
    })
    assert fan_speed_to_raw(50, mapping) == "low"


def test_string_raw_values_are_normalized_like_tuya_local():
    mapping = validate_fan_speed_mapping({
        "raw_type": "string",
        "rules": [
            {"dps_val": 1, "value": 40},
            {"dps_val": 2, "value": 100},
        ],
    })
    assert mapping is not None
    assert mapping["rules"][0]["dps_val"] == "1"
    assert fan_speed_from_raw(1, mapping) == 40


def test_oscillation_supports_multiple_false_raws():
    mapping = validate_fan_oscillation_mapping({
        "raw_type": "string",
        "rules": [
            {"dps_val": "90", "value": False},
            {"dps_val": "45", "value": False},
            {"dps_val": "45_90", "value": True},
        ],
    })
    assert mapping is not None
    assert fan_oscillation_from_raw("90", mapping) is False
    assert fan_oscillation_from_raw("45", mapping) is False
    assert fan_oscillation_to_raw(False, mapping) == "90"
    assert fan_oscillation_to_raw(True, mapping) == "45_90"


def test_oscillation_fallback_is_read_only():
    mapping = validate_fan_oscillation_mapping({
        "raw_type": "string",
        "rules": [
            {"dps_val": "0_90", "value": True},
            {"dps_val": "90", "value": False},
            {"value": False},
        ],
    })
    assert mapping is not None
    assert fan_oscillation_from_raw("unexpected", mapping) is False
    assert fan_oscillation_to_raw(False, mapping) == "90"


def test_invalid_or_unwritable_mapping_fails_closed():
    assert validate_fan_speed_mapping({
        "raw_type": "string",
        "rules": [{"dps_val": "x", "value": 0}, {"dps_val": "y", "value": 100}],
    }) is None
    assert validate_fan_oscillation_mapping({
        "raw_type": "string",
        "rules": [{"dps_val": "x", "value": False}, {"value": True}],
    }) is None
