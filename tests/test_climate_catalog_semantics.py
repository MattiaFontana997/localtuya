"""Regression tests for catalog-driven Tuya Local climate semantics."""

import unittest
from unittest.mock import AsyncMock

from homeassistant.components.climate.const import HVACMode, PRESET_ECO

from custom_components.localtuya.climate import LocaltuyaClimate, _catalog_value_map
from custom_components.localtuya.const import (
    CONF_HVAC_MODE_DP, CONF_HVAC_MODE_VALUES, CONF_PRESET_DP, CONF_PRESET_VALUES,
    CONF_TARGET_TEMPERATURE_LOW_DP, CONF_TARGET_TEMPERATURE_HIGH_DP,
    CONF_TARGET_TEMPERATURE_LOW_PRECISION, CONF_TARGET_TEMPERATURE_HIGH_PRECISION,
)


class ClimateCatalogSemanticsTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def bare(config):
        entity = object.__new__(LocaltuyaClimate)
        entity._config = config
        entity._dp_id = config.get("id", 1)
        entity._state = True
        entity._last_non_off_hvac_mode = None
        entity.warning = lambda *args, **kwargs: None
        entity.has_config = lambda key: key in entity._config
        entity._device = type("Device", (), {"set_dp": AsyncMock(), "set_dps": AsyncMock()})()
        return entity

    def test_dynamic_hvac_map_preserves_exact_raw_values(self):
        result = _catalog_value_map(
            {CONF_HVAC_MODE_VALUES: {"off": "PowerOff", "heat": "Heating"}},
            CONF_HVAC_MODE_VALUES, enum_type=HVACMode,
        )
        self.assertEqual(result[HVACMode.OFF], "PowerOff")
        self.assertEqual(result[HVACMode.HEAT], "Heating")

    async def test_enum_off_writes_raw_off_instead_of_false(self):
        entity = self.bare({"id": 1, CONF_HVAC_MODE_DP: 1})
        entity._conf_hvac_mode_dp = 1
        entity._conf_hvac_mode_set = {HVACMode.OFF: "off", HVACMode.HEAT: "heat"}
        await entity.async_set_hvac_mode(HVACMode.OFF)
        entity._device.set_dp.assert_awaited_once_with("off", 1)

    async def test_eco_can_be_regular_preset_mapping(self):
        entity = self.bare({"id": 1, CONF_PRESET_DP: 6, CONF_PRESET_VALUES: {"eco": True, "comfort": False}})
        entity._conf_eco_dp = None
        entity._conf_preset_dp = 6
        entity._conf_preset_set = {"eco": True, "comfort": False}
        await entity.async_set_preset_mode(PRESET_ECO)
        entity._device.set_dp.assert_awaited_once_with(True, 6)

    async def test_target_range_scales_independently(self):
        entity = self.bare({
            "id": 1,
            CONF_TARGET_TEMPERATURE_LOW_DP: 10,
            CONF_TARGET_TEMPERATURE_HIGH_DP: 11,
            CONF_TARGET_TEMPERATURE_LOW_PRECISION: 0.1,
            CONF_TARGET_TEMPERATURE_HIGH_PRECISION: 0.01,
        })
        entity._target_precision = 1.0
        entity._target_low_precision = 0.1
        entity._target_high_precision = 0.01
        await entity.async_set_temperature(target_temp_low=18.5, target_temp_high=23.25)
        entity._device.set_dps.assert_awaited_once_with({10: 185, 11: 2325})


if __name__ == "__main__":
    unittest.main()
