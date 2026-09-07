from custom_components.localtuya.binary_sensor import (
    evaluate_binary_sensor_mapping,
    validate_binary_sensor_mapping,
)


def test_bitfield_mask_mapping_matches_any_set_bit():
    mapping = [
        {"dps_val": 4, "value": True},
        {"value": False},
    ]
    assert evaluate_binary_sensor_mapping(0, mapping, bitfield=True) is False
    assert evaluate_binary_sensor_mapping(4, mapping, bitfield=True) is True
    assert evaluate_binary_sensor_mapping(5, mapping, bitfield=True) is True
    assert evaluate_binary_sensor_mapping(8, mapping, bitfield=True) is False


def test_bitfield_rule_order_matches_tuya_local_semantics():
    mapping = [
        {"dps_val": 0, "value": False},
        {"dps_val": 1, "value": False},
        {"dps_val": 2, "value": False},
        {"value": True},
    ]
    assert evaluate_binary_sensor_mapping(0, mapping, bitfield=True) is False
    assert evaluate_binary_sensor_mapping(1, mapping, bitfield=True) is False
    assert evaluate_binary_sensor_mapping(3, mapping, bitfield=True) is False
    assert evaluate_binary_sensor_mapping(4, mapping, bitfield=True) is True


def test_integer_mapping_supports_default_catch_all():
    mapping = [
        {"dps_val": 4, "value": True},
        {"value": False},
    ]
    assert evaluate_binary_sensor_mapping(4, mapping) is True
    assert evaluate_binary_sensor_mapping(3, mapping) is False


def test_string_mapping_supports_multiple_true_states():
    mapping = [
        {"dps_val": "small_move", "value": True},
        {"dps_val": "large_move", "value": True},
        {"value": False},
    ]
    assert evaluate_binary_sensor_mapping("small_move", mapping) is True
    assert evaluate_binary_sensor_mapping("large_move", mapping) is True
    assert evaluate_binary_sensor_mapping("none", mapping) is False


def test_explicit_null_rule_is_evaluated_before_default():
    mapping = [
        {"dps_val": None, "value": False},
        {"value": True},
    ]
    assert evaluate_binary_sensor_mapping(None, mapping, bitfield=True) is False
    assert evaluate_binary_sensor_mapping(4, mapping, bitfield=True) is True


def test_invalid_mapping_fails_closed():
    mapping = [{"dps_val": 1, "value": "yes"}]
    assert validate_binary_sensor_mapping(mapping) is None
    assert evaluate_binary_sensor_mapping(1, mapping) is None


def test_bitfield_rejects_non_integer_masks():
    mapping = [{"dps_val": "4", "value": True}, {"value": False}]
    assert validate_binary_sensor_mapping(mapping, bitfield=True) is None


def test_mapping_without_match_or_default_is_unknown():
    mapping = [{"dps_val": "alarm", "value": True}]
    assert evaluate_binary_sensor_mapping("normal", mapping) is None


def load_tests(loader, tests, pattern):
    """Include function regressions in the project's unittest CI runner."""
    import unittest

    tests.addTests(unittest.FunctionTestCase(test) for name, test in globals().items()
                   if name.startswith("test_") and callable(test))
    return tests
