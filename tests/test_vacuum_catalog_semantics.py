"""Regression tests for catalog-driven Tuya Local vacuum semantics."""

import unittest
from unittest.mock import AsyncMock

from custom_components.localtuya.const import (
    CONF_FAN_SPEED_DP,
    CONF_LOCATE_DP,
    CONF_VACUUM_ACTIVATE_DP,
    CONF_VACUUM_COMMAND_DP,
    CONF_VACUUM_DIRECTION_DP,
    CONF_VACUUM_POWER_DP,
)
from custom_components.localtuya.vacuum import LocaltuyaVacuum, _decode_scalar


class VacuumCatalogSemanticsTests(unittest.IsolatedAsyncioTestCase):
    def _vacuum(self):
        vacuum = object.__new__(LocaltuyaVacuum)
        vacuum._catalog_mode = True
        vacuum._config = {
            CONF_VACUUM_COMMAND_DP: 2,
            CONF_VACUUM_ACTIVATE_DP: 3,
            CONF_VACUUM_POWER_DP: 4,
            CONF_VACUUM_DIRECTION_DP: 5,
            CONF_LOCATE_DP: 6,
            CONF_FAN_SPEED_DP: 7,
        }
        vacuum._command_values = {"start": "go", "pause": "hold", "return_to_base": "dock", "stop": "halt"}
        vacuum._direction_values = {"left": "L", "stop": "S"}
        vacuum._fan_speed_values = {"quiet": "q", "turbo": "t"}
        vacuum._activate_on = "on"
        vacuum._activate_off = "off"
        vacuum._power_on = True
        vacuum._power_off = False
        vacuum._locate_on = True
        vacuum._attr_fan_speed_list = list(vacuum._fan_speed_values)
        vacuum._device = type("Device", (), {"set_dp": AsyncMock()})()
        vacuum.has_config = lambda key: key in vacuum._config
        vacuum.warning = lambda *args, **kwargs: None
        return vacuum

    def test_raw_status_decodes_to_friendly(self):
        self.assertEqual(_decode_scalar({"charging": "charge"}, "charge"), "charging")
        self.assertEqual(_decode_scalar({}, "sleep"), "sleep")

    async def test_start_prefers_command_mapping(self):
        vacuum = self._vacuum()
        await vacuum.async_start()
        vacuum._device.set_dp.assert_awaited_once_with("go", 2)

    async def test_pause_falls_back_to_activate(self):
        vacuum = self._vacuum()
        vacuum._command_values.pop("pause")
        await vacuum.async_pause()
        vacuum._device.set_dp.assert_awaited_once_with("off", 3)

    async def test_fan_speed_writes_exact_raw_value(self):
        vacuum = self._vacuum()
        await vacuum.async_set_fan_speed("turbo")
        vacuum._device.set_dp.assert_awaited_once_with("t", 7)

    async def test_send_stop_prefers_direction_mapping(self):
        vacuum = self._vacuum()
        await vacuum.async_send_command("stop")
        vacuum._device.set_dp.assert_awaited_once_with("S", 5)

    async def test_locate_uses_boolean_trigger(self):
        vacuum = self._vacuum()
        await vacuum.async_locate()
        vacuum._device.set_dp.assert_awaited_once_with(True, 6)


if __name__ == "__main__":
    unittest.main()
