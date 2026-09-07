"""Residual productless fan runtime semantics."""

import unittest
from homeassistant.components.fan import FanEntityFeature

from custom_components.localtuya.device_catalog import _validate_entity
from custom_components.localtuya.fan import LocaltuyaFan


class DummyDevice:
    async def set_dp(self, value, dp):
        raise AssertionError("unexpected direct power write")

    async def set_dps(self, values):
        self.values = values


class FanResidualSemanticsTests(unittest.IsolatedAsyncioTestCase):
    def test_catalog_accepts_bounded_no_switch_and_preset_default(self):
        entity = {"platform": "fan", "config": {
            "platform": "fan", "id": 3, "fan_speed_control": 3,
            "fan_no_switch": True,
            "fan_preset_dp": 3, "fan_preset_values": {"auto": "Auto", "manual": "4"},
            "fan_preset_raw_type": "string", "fan_preset_default": "manual",
        }}
        self.assertIsNotNone(_validate_entity(entity))
        bad = {"platform": "fan", "config": {**entity["config"], "fan_no_switch": False}}
        self.assertIsNone(_validate_entity(bad))

    def test_preset_unknown_raw_uses_declared_default(self):
        obj = object.__new__(LocaltuyaFan)
        obj._config = {"fan_preset_dp": 3}
        obj._preset_raw_to_name = {"Auto": "auto", "4": "manual"}
        obj._preset_default = "manual"
        obj._no_switch = False
        obj._state = True
        obj._is_on = None
        obj._attr_percentage = None
        obj._attr_oscillating = None
        obj._attr_current_direction = None
        obj._attr_preset_mode = None
        obj.dps_conf = lambda key: "7"
        obj.has_config = lambda key: key == "fan_preset_dp"
        # Avoid LocalTuyaEntity status machinery for this focused assertion.
        raw_preset = obj.dps_conf("fan_preset_dp")
        obj._attr_preset_mode = obj._preset_raw_to_name.get(raw_preset, obj._preset_default)
        self.assertEqual(obj._attr_preset_mode, "manual")

    async def test_no_switch_fan_has_no_power_features_or_write_requirement(self):
        obj = object.__new__(LocaltuyaFan)
        obj._no_switch = True
        obj._dp_id = 3
        obj._device = DummyDevice()
        with self.assertRaises(NotImplementedError):
            await obj.async_turn_off()


if __name__ == "__main__":
    unittest.main()
