"""Regression tests for Tuya Local-compatible fan catalog semantics."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from homeassistant.components.fan import FanEntityFeature

from custom_components.localtuya.const import (
    CONF_FAN_OSCILLATING_CONTROL,
    CONF_FAN_OSCILLATING_OFF,
    CONF_FAN_OSCILLATING_ON,
    CONF_FAN_PRESET_DP,
    CONF_FAN_PRESET_VALUES,
)
from custom_components.localtuya.fan import LocaltuyaFan


class FanTuyaLocalSemanticsTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _bare(config):
        fan = object.__new__(LocaltuyaFan)
        fan._config = config
        fan.warning = lambda *args, **kwargs: None
        return fan

    def test_catalog_presets_preserve_exact_raw_values(self):
        fan = self._bare({CONF_FAN_PRESET_VALUES: {
            "normal": "Normal",
            "fresh": "Breeze",
        }})
        self.assertEqual(
            fan._configured_preset_values(),
            {"normal": "Normal", "fresh": "Breeze"},
        )

    def test_invalid_and_duplicate_presets_are_ignored(self):
        fan = self._bare({CONF_FAN_PRESET_VALUES: {
            "normal": "Normal",
            "duplicate": "Normal",
            "": "Bad",
        }})
        self.assertEqual(fan._configured_preset_values(), {"normal": "Normal"})

    async def test_mapped_oscillation_writes_exact_raw_value(self):
        fan = self._bare({
            CONF_FAN_OSCILLATING_CONTROL: 7,
            CONF_FAN_OSCILLATING_ON: "on",
            CONF_FAN_OSCILLATING_OFF: "off",
        })
        fan._oscillating_on = "on"
        fan._oscillating_off = "off"
        fan._device = type("Device", (), {"set_dp": AsyncMock()})()
        fan.has_config = lambda key: key in fan._config

        await fan.async_oscillate(True)
        fan._device.set_dp.assert_awaited_once_with("on", 7)

    async def test_set_preset_writes_exact_raw_value(self):
        fan = self._bare({CONF_FAN_PRESET_DP: 2})
        fan._preset_values = {"fresh": "Breeze"}
        fan._device = type("Device", (), {"set_dp": AsyncMock()})()
        fan.has_config = lambda key: key in fan._config

        await fan.async_set_preset_mode("fresh")
        fan._device.set_dp.assert_awaited_once_with("Breeze", 2)

    def test_preset_feature_constant_is_available(self):
        self.assertTrue(FanEntityFeature.PRESET_MODE)


if __name__ == "__main__":
    unittest.main()
