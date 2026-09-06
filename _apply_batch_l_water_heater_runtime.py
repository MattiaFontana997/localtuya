from pathlib import Path

path = Path('custom_components/localtuya/water_heater.py')
text = path.read_text(encoding='utf-8')

old = '''            await self._device.set_dp(\n                _unscaled(kwargs[ATTR_TEMPERATURE], self._scaling),\n                dp_id,\n            )'''
new = '''            raw_value = _unscaled(kwargs[ATTR_TEMPERATURE], self._scaling)\n            if self.has_advanced_mapping(dp_id):\n                await self.set_mapped_dp(raw_value, dp_id)\n            else:\n                await self._device.set_dp(raw_value, dp_id)'''
if old not in text:
    raise SystemExit('temperature write marker missing')
text = text.replace(old, new, 1)

old = '''        if dp_id is None or operation_mode not in self._mode_values:\n            raise NotImplementedError()\n        await self._device.set_dp(self._mode_values[operation_mode], dp_id)'''
new = '''        if dp_id is None or operation_mode not in self._mode_values:\n            raise NotImplementedError()\n        raw_value = self._mode_values[operation_mode]\n        if self.has_advanced_mapping(dp_id):\n            await self.set_mapped_dp(raw_value, dp_id)\n        else:\n            await self._device.set_dp(raw_value, dp_id)'''
if old not in text:
    raise SystemExit('operation mode write marker missing')
text = text.replace(old, new, 1)

old = '''        if away_dp is not None:\n            await self._device.set_dp(self._away_on, away_dp)\n            return'''
new = '''        if away_dp is not None:\n            if self.has_advanced_mapping(away_dp):\n                await self.set_mapped_dp(self._away_on, away_dp)\n            else:\n                await self._device.set_dp(self._away_on, away_dp)\n            return'''
if old not in text:
    raise SystemExit('away on marker missing')
text = text.replace(old, new, 1)

old = '''        if away_dp is not None:\n            await self._device.set_dp(self._away_off, away_dp)\n            return'''
new = '''        if away_dp is not None:\n            if self.has_advanced_mapping(away_dp):\n                await self.set_mapped_dp(self._away_off, away_dp)\n            else:\n                await self._device.set_dp(self._away_off, away_dp)\n            return'''
if old not in text:
    raise SystemExit('away off marker missing')
text = text.replace(old, new, 1)

path.write_text(text, encoding='utf-8')

test = Path('tests/test_water_heater_advanced_mapping.py')
test.write_text('''"""Regression tests for mapping-aware water-heater writes."""\n\nimport unittest\nfrom unittest.mock import AsyncMock\n\nfrom homeassistant.const import ATTR_TEMPERATURE\n\nfrom custom_components.localtuya.const import (\n    CONF_WATER_HEATER_AWAY_DP,\n    CONF_WATER_HEATER_MODE_DP,\n    CONF_WATER_HEATER_TARGET_TEMPERATURE_DP,\n)\nfrom custom_components.localtuya.water_heater import LocaltuyaWaterHeater\n\n\nclass WaterHeaterAdvancedMappingTests(unittest.IsolatedAsyncioTestCase):\n    @staticmethod\n    def _bare(config):\n        heater = object.__new__(LocaltuyaWaterHeater)\n        heater._config = config\n        heater._device = type("Device", (), {"set_dp": AsyncMock()})()\n        heater.has_advanced_mapping = lambda dp: True\n        heater.set_mapped_dp = AsyncMock()\n        return heater\n\n    async def test_operation_mode_uses_mapping_aware_write(self):\n        heater = self._bare({CONF_WATER_HEATER_MODE_DP: 1})\n        heater._mode_values = {"eco": "eco"}\n        await heater.async_set_operation_mode("eco")\n        heater.set_mapped_dp.assert_awaited_once_with("eco", 1)\n        heater._device.set_dp.assert_not_awaited()\n\n    async def test_target_temperature_preserves_raw_scaling_before_mapping(self):\n        heater = self._bare({CONF_WATER_HEATER_TARGET_TEMPERATURE_DP: 2})\n        heater._scaling = 0.1\n        await heater.async_set_temperature(**{ATTR_TEMPERATURE: 55})\n        heater.set_mapped_dp.assert_awaited_once_with(550, 2)\n        heater._device.set_dp.assert_not_awaited()\n\n    async def test_away_mode_uses_mapping_aware_write(self):\n        heater = self._bare({CONF_WATER_HEATER_AWAY_DP: 3})\n        heater._away_on = "away"\n        await heater.async_turn_away_mode_on()\n        heater.set_mapped_dp.assert_awaited_once_with("away", 3)\n        heater._device.set_dp.assert_not_awaited()\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding='utf-8')
