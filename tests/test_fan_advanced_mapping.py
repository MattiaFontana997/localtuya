"""Fan regressions for conditional advanced mapping metadata."""

import unittest

from custom_components.localtuya.const import CONF_FAN_SPEED_CONTROL
from custom_components.localtuya.fan import LocaltuyaFan


class _Device:
    def __init__(self):
        self.single = None
        self.multi = None
    async def set_dp(self, value, dp):
        self.single = (value, dp)
    async def set_dps(self, states):
        self.multi = dict(states)


class FanAdvancedMappingTests(unittest.IsolatedAsyncioTestCase):
    def _fan(self):
        fan = LocaltuyaFan.__new__(LocaltuyaFan)
        fan._config = {CONF_FAN_SPEED_CONTROL: 2}
        fan._dp_id = 1
        fan._is_on = True
        fan._speed_mapping = None
        fan._use_ordered_list = False
        fan._ordered_list = []
        fan._speed_range = (1, 12)
        fan._dps_type = int
        fan._advanced_mapping = []
        fan._advanced_mapping_by_dp = {"2": [{"constraint_dp": 3, "conditions": [{"dps_val": "nature", "step": 4}, {"dps_val": "sleep", "step": 4}]}]}
        fan._status = {"1": True, "2": 7, "3": "nature"}
        fan._device = _Device()
        return fan

    async def test_percentage_write_is_quantized_by_active_step(self):
        fan = self._fan()
        await fan.async_set_percentage(50)
        self.assertEqual(fan._device.single, (8, 2))
        self.assertIsNone(fan._device.multi)

    def test_speed_count_follows_active_step(self):
        fan = self._fan()
        fan._refresh_speed_count()
        self.assertEqual(fan._attr_speed_count, 3)
        fan._status["3"] = "normal"
        fan._refresh_speed_count()
        self.assertEqual(fan._attr_speed_count, 12)


if __name__ == "__main__":
    unittest.main()
