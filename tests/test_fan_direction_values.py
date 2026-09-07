
"""Exact catalog-provided fan direction mappings."""

import unittest

from custom_components.localtuya.device_catalog import _validate_entity
from custom_components.localtuya.fan import LocaltuyaFan
from custom_components.localtuya.fan_mapping import validate_fan_direction_values


class DummyDevice:
    def __init__(self):
        self.write = None

    async def set_dp(self, value, dp):
        self.write = (value, dp)


class FanDirectionValuesTests(unittest.IsolatedAsyncioTestCase):
    def test_validator_preserves_exact_three_way_mapping(self):
        values = {"forward": "in", "reverse": "out", "exchange": "exch"}
        self.assertEqual(validate_fan_direction_values(values), values)
        self.assertIsNone(validate_fan_direction_values({"forward": "in", "exchange": "exch"}))
        self.assertIsNone(validate_fan_direction_values({"forward": "in", "reverse": "in"}))

    def test_catalog_accepts_only_bounded_exact_direction_values(self):
        entity = {"platform": "fan", "config": {
            "platform": "fan", "id": 1, "fan_direction": 2,
            "fan_direction_values": {
                "forward": "in", "reverse": "out", "exchange": "exch",
            },
        }}
        validated = _validate_entity(entity)
        self.assertIsNotNone(validated)
        self.assertEqual(validated["config"]["fan_direction_values"]["exchange"], "exch")
        bad = {"platform": "fan", "config": {
            "platform": "fan", "id": 1, "fan_direction": 2,
            "fan_direction_values": {"forward": "in", "reverse": "in"},
        }}
        self.assertIsNone(_validate_entity(bad))

    async def test_exchange_write_uses_exact_raw_value(self):
        obj = object.__new__(LocaltuyaFan)
        obj._config = {"fan_direction": 2}
        obj._direction_values = {
            "forward": "in", "reverse": "out", "exchange": "exch",
        }
        obj._device = DummyDevice()
        obj.has_config = lambda key: key == "fan_direction"
        await obj.async_set_direction("exchange")
        self.assertEqual(obj._device.write, ("exch", 2))
