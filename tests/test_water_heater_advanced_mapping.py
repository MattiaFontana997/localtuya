"""Regression tests for mapping-aware water-heater writes."""

import unittest
from unittest.mock import AsyncMock

from homeassistant.const import ATTR_TEMPERATURE

from custom_components.localtuya.const import (
    CONF_WATER_HEATER_AWAY_DP,
    CONF_WATER_HEATER_MODE_DP,
    CONF_WATER_HEATER_TARGET_TEMPERATURE_DP,
)
from custom_components.localtuya.water_heater import LocaltuyaWaterHeater


class WaterHeaterAdvancedMappingTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _bare(config):
        heater = object.__new__(LocaltuyaWaterHeater)
        heater._config = config
        heater._device = type("Device", (), {"set_dp": AsyncMock()})()
        heater.has_advanced_mapping = lambda dp: True
        heater.set_mapped_dp = AsyncMock()
        return heater

    async def test_operation_mode_uses_mapping_aware_write(self):
        heater = self._bare({CONF_WATER_HEATER_MODE_DP: 1})
        heater._mode_values = {"eco": "eco"}
        await heater.async_set_operation_mode("eco")
        heater.set_mapped_dp.assert_awaited_once_with("eco", 1)
        heater._device.set_dp.assert_not_awaited()

    async def test_target_temperature_preserves_raw_scaling_before_mapping(self):
        heater = self._bare({CONF_WATER_HEATER_TARGET_TEMPERATURE_DP: 2})
        heater._scaling = 0.1
        await heater.async_set_temperature(**{ATTR_TEMPERATURE: 55})
        heater.set_mapped_dp.assert_awaited_once_with(550, 2)
        heater._device.set_dp.assert_not_awaited()

    async def test_away_mode_uses_mapping_aware_write(self):
        heater = self._bare({CONF_WATER_HEATER_AWAY_DP: 3})
        heater._away_on = "away"
        await heater.async_turn_away_mode_on()
        heater.set_mapped_dp.assert_awaited_once_with("away", 3)
        heater._device.set_dp.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
