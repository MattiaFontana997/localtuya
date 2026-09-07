"""Read-only transforms and exact upstream raw matching regressions."""

import unittest
from custom_components.localtuya.sensor_mapping import (
    evaluate_sensor_value_mapping, validate_sensor_value_mapping,
)
from custom_components.localtuya.device_catalog import _validate_entity
from custom_components.localtuya.sensor import LocaltuyaSensor


class SensorMappingTests(unittest.TestCase):
    def spec(self, rules, **extra):
        spec = validate_sensor_value_mapping({"raw_type": "string", "rules": rules, **extra})
        self.assertIsNotNone(spec)
        return spec

    def test_enum_numeric_and_unknown_raw_preservation(self):
        spec = self.spec([{"dps_val": "low", "value": 20}, {"dps_val": "high", "value": 80}])
        self.assertEqual(evaluate_sensor_value_mapping("high", spec)[0], 80)
        self.assertEqual(evaluate_sensor_value_mapping("other", spec)[0], "other")

    def test_null_specific_scale_and_last_default(self):
        spec = self.spec([{"value": -1}, {"scale": 1000}, {"dps_val": None, "value": 0}])
        self.assertEqual(evaluate_sensor_value_mapping(None, spec)[0], 0)
        self.assertEqual(evaluate_sensor_value_mapping(1234, spec)[0], 1.234)

    def test_raw_matching_does_not_equate_boolean_integer_or_float(self):
        spec = self.spec([{"dps_val": True, "value": 11}, {"dps_val": 1, "value": 22}, {"dps_val": 1.0, "value": 33}])
        for raw, expected in [(True, 11), (1, 22), (1.0, 33), ("1", 22)]:
            self.assertEqual(evaluate_sensor_value_mapping(raw, spec)[0], expected)

    def test_transform_order_invert_project_scale_and_no_rounding(self):
        spec = self.spec([{"invert": True, "target_range": {"min": 10, "max": 20}, "scale": 3}], range={"min": 0, "max": 100})
        self.assertEqual(evaluate_sensor_value_mapping(25, spec)[0], 17.5 / 3)

    def test_nonfinite_unknown_and_executable_shapes_rejected(self):
        for rule in [{"scale": float("nan")}, {"scale": float("inf")}, {"scale": 0}, {"value": float("inf")}, {"expression": "raw * 2"}, {"conditions": []}, {"target_range": {"min": 0, "max": 1}}]:
            self.assertIsNone(validate_sensor_value_mapping({"raw_type": "integer", "rules": [rule]}))

    def test_runtime_sensor_no_secondary_rounding_and_icon_reset(self):
        sensor = object.__new__(LocaltuyaSensor)
        sensor._dp_id = 1
        sensor._config = {}
        sensor._value_mapping = self.spec([{"scale": 1000}, {"dps_val": 2, "value": 50, "icon": "mdi:cup"}])
        sensor.dps = lambda dp: 1234
        sensor.status_updated()
        self.assertEqual(sensor.native_value, 1.234)
        sensor.dps = lambda dp: 2
        sensor.status_updated()
        self.assertEqual(sensor._mapping_icon, "mdi:cup")
        sensor.dps = lambda dp: 1234
        sensor.status_updated()
        self.assertIsNone(sensor._mapping_icon)

    def test_catalog_rejects_double_transform_and_wrong_platform(self):
        spec = self.spec([{"scale": 10}])
        for platform, extra in [("number", {}), ("sensor", {"scaling": .1}), ("sensor", {"advanced_mapping_by_dp": {"1": [{"scale": 10}]}})]:
            self.assertIsNone(_validate_entity({"platform": platform, "config": {"platform": platform, "id": 1, "sensor_value_mapping": spec, **extra}}))
