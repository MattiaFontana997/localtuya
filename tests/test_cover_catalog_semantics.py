"""Regression tests for catalog-driven Tuya Local cover semantics."""

import unittest
from unittest.mock import AsyncMock

from custom_components.localtuya.cover import (
    LocaltuyaCover, _percent_to_range, _range_to_percent
)
from custom_components.localtuya.const import (
    CONF_SET_POSITION_DP, CONF_SET_POSITION_MIN, CONF_SET_POSITION_MAX,
    CONF_SET_POSITION_STEP, CONF_SET_POSITION_INVERTED,
    CONF_TILT_POSITION_DP, CONF_TILT_POSITION_MIN, CONF_TILT_POSITION_MAX,
)


class CoverCatalogSemanticsTests(unittest.IsolatedAsyncioTestCase):
    def test_native_position_ranges_convert_exactly(self):
        self.assertEqual(_range_to_percent(25, 0, 100, False), 25)
        self.assertEqual(_range_to_percent(25, 0, 100, True), 75)
        self.assertEqual(_range_to_percent(5, 0, 10, False), 50)
        self.assertEqual(_percent_to_range(75, 0, 100, 5, False), 75)
        self.assertEqual(_percent_to_range(25, 0, 100, 1, True), 75)

    async def test_set_position_uses_catalog_range_and_inversion(self):
        cover = object.__new__(LocaltuyaCover)
        cover._config = {
            CONF_SET_POSITION_DP: 2, CONF_SET_POSITION_MIN: 0,
            CONF_SET_POSITION_MAX: 100, CONF_SET_POSITION_STEP: 5,
            CONF_SET_POSITION_INVERTED: True,
        }
        cover._positioning_mode = "position"
        cover._position_inverted = False
        cover._device = type("Device", (), {"set_dp": AsyncMock()})()
        cover.has_config = lambda key: key in cover._config
        cover._cancel_stop_task = lambda: None
        cover.debug = lambda *args, **kwargs: None
        cover.warning = lambda *args, **kwargs: None
        await cover.async_set_cover_position(position=25)
        cover._device.set_dp.assert_awaited_once_with(75, 2)

    async def test_tilt_uses_native_range(self):
        cover = object.__new__(LocaltuyaCover)
        cover._config = {
            CONF_TILT_POSITION_DP: 5, CONF_TILT_POSITION_MIN: 10,
            CONF_TILT_POSITION_MAX: 50,
        }
        cover._device = type("Device", (), {"set_dp": AsyncMock()})()
        await cover.async_set_cover_tilt_position(tilt_position=50)
        cover._device.set_dp.assert_awaited_once_with(30, 5)


if __name__ == "__main__":
    unittest.main()
