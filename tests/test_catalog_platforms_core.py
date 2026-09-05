"""Regression tests for catalog-driven core platform runtimes."""

import unittest
from unittest.mock import AsyncMock

from custom_components.localtuya.button import LocaltuyaButton
from custom_components.localtuya.const import (
    CONF_BUTTON_PRESS_VALUE,
    CONF_HUMIDIFIER_ACTION_DP,
    CONF_HUMIDIFIER_ACTION_VALUES,
    CONF_HUMIDIFIER_CURRENT_HUMIDITY_DP,
    CONF_HUMIDIFIER_HUMIDITY_SCALING,
    CONF_HUMIDIFIER_MODE_DP,
    CONF_HUMIDIFIER_MODE_VALUES,
    CONF_HUMIDIFIER_SWITCH_DP,
    CONF_HUMIDIFIER_SWITCH_OFF,
    CONF_HUMIDIFIER_SWITCH_ON,
    CONF_HUMIDIFIER_TARGET_HUMIDITY_DP,
    CONF_LOCK_COMMAND_VALUES,
    CONF_LOCK_JAMMED_DP,
    CONF_LOCK_JAMMED_VALUES,
    CONF_LOCK_OPEN_DP,
    CONF_LOCK_OPEN_VALUES,
    CONF_LOCK_STATE_DP,
    CONF_LOCK_STATE_VALUES,
    CONF_TEXT_MAX,
    CONF_TEXT_MIN,
    CONF_VALVE_CURRENT_POSITION_DP,
    CONF_VALVE_POSITION_CONTROL,
    CONF_VALVE_POSITION_INVERTED,
    CONF_VALVE_POSITION_MAX,
    CONF_VALVE_POSITION_MIN,
)
from custom_components.localtuya.humidifier import LocaltuyaHumidifier
from custom_components.localtuya.lock import LocaltuyaLock
from custom_components.localtuya.text import LocaltuyaText
from custom_components.localtuya.valve import LocaltuyaValve, _position_from_raw, _position_to_raw


class _Device:
    def __init__(self):
        self.set_dp = AsyncMock()
        self.is_connecting = False


def _entity(cls, config, state):
    entity = object.__new__(cls)
    entity._config = config
    entity._dp_id = config["id"]
    entity._device = _Device()
    entity.has_config = lambda key: key in config and config[key] is not None
    entity.dps = lambda dp: state.get(dp)
    entity.warning = lambda *args, **kwargs: None
    return entity


class CorePlatformRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_button_uses_exact_press_value(self):
        button = _entity(LocaltuyaButton, {"id": 4, CONF_BUTTON_PRESS_VALUE: "reset"}, {})
        button._press_value = "reset"
        await button.async_press()
        button._device.set_dp.assert_awaited_once_with("reset", 4)

    async def test_text_round_trip(self):
        text = _entity(LocaltuyaText, {"id": 8, CONF_TEXT_MIN: 1, CONF_TEXT_MAX: 32}, {8: "hello"})
        text._state = None
        text.status_updated()
        self.assertEqual(text.native_value, "hello")
        await text.async_set_value("world")
        text._device.set_dp.assert_awaited_once_with("world", 8)

    def test_valve_position_scaling_and_inversion(self):
        self.assertEqual(_position_from_raw(20, 20, 80, False), 0)
        self.assertEqual(_position_from_raw(80, 20, 80, False), 100)
        self.assertEqual(_position_from_raw(20, 20, 80, True), 100)
        self.assertEqual(_position_to_raw(50, 20, 80, False), 50)

    async def test_valve_writes_exact_scaled_position(self):
        config = {
            "id": 10,
            CONF_VALVE_POSITION_CONTROL: True,
            CONF_VALVE_POSITION_MIN: 20,
            CONF_VALVE_POSITION_MAX: 80,
            CONF_VALVE_POSITION_INVERTED: False,
            CONF_VALVE_CURRENT_POSITION_DP: 11,
        }
        valve = _entity(LocaltuyaValve, config, {10: 20, 11: 50})
        valve._position_control = True
        valve._position_min = 20.0
        valve._position_max = 80.0
        valve._position_inverted = False
        valve._open_value = True
        valve._closed_value = False
        valve._switch_on = True
        valve._switch_off = False
        self.assertEqual(valve.current_valve_position, 50)
        await valve.async_set_valve_position(100)
        valve._device.set_dp.assert_awaited_once_with(80, 10)

    async def test_lock_uses_exact_catalog_values(self):
        config = {
            "id": 1,
            CONF_LOCK_COMMAND_VALUES: {"lock": "secure", "unlock": "release"},
            CONF_LOCK_STATE_DP: 2,
            CONF_LOCK_STATE_VALUES: {"locked": "closed", "unlocked": "open"},
            CONF_LOCK_OPEN_DP: 3,
            CONF_LOCK_OPEN_VALUES: {"open": 1, "closed": 0},
            CONF_LOCK_JAMMED_DP: 4,
            CONF_LOCK_JAMMED_VALUES: {"jammed": "jam", "clear": "ok"},
        }
        lock = _entity(LocaltuyaLock, config, {2: "closed", 3: 0, 4: "jam"})
        lock._command_values = config[CONF_LOCK_COMMAND_VALUES]
        lock._state_values = config[CONF_LOCK_STATE_VALUES]
        lock._open_values = config[CONF_LOCK_OPEN_VALUES]
        lock._jammed_values = config[CONF_LOCK_JAMMED_VALUES]
        self.assertTrue(lock.is_locked)
        self.assertFalse(lock.is_open)
        self.assertTrue(lock.is_jammed)
        await lock.async_unlock()
        lock._device.set_dp.assert_awaited_once_with("release", 1)

    async def test_humidifier_scaling_mode_and_action(self):
        config = {
            "id": 5,
            CONF_HUMIDIFIER_SWITCH_DP: 1,
            CONF_HUMIDIFIER_SWITCH_ON: "on",
            CONF_HUMIDIFIER_SWITCH_OFF: "off",
            CONF_HUMIDIFIER_CURRENT_HUMIDITY_DP: 2,
            CONF_HUMIDIFIER_TARGET_HUMIDITY_DP: 3,
            CONF_HUMIDIFIER_HUMIDITY_SCALING: 0.1,
            CONF_HUMIDIFIER_MODE_DP: 4,
            CONF_HUMIDIFIER_MODE_VALUES: {"auto": "A", "sleep": "S"},
            CONF_HUMIDIFIER_ACTION_DP: 5,
            CONF_HUMIDIFIER_ACTION_VALUES: {"humidifying": "work"},
        }
        humidifier = _entity(LocaltuyaHumidifier, config, {1: "on", 2: 455, 3: 600, 4: "S", 5: "work"})
        humidifier._scaling = 0.1
        humidifier._switch_on = "on"
        humidifier._switch_off = "off"
        humidifier._mode_values = config[CONF_HUMIDIFIER_MODE_VALUES]
        humidifier._action_values = config[CONF_HUMIDIFIER_ACTION_VALUES]
        self.assertEqual(humidifier.current_humidity, 45.5)
        self.assertEqual(humidifier.target_humidity, 60.0)
        self.assertEqual(humidifier.mode, "sleep")
        self.assertEqual(humidifier.action.value, "humidifying")
        await humidifier.async_set_mode("auto")
        humidifier._device.set_dp.assert_awaited_once_with("A", 4)


if __name__ == "__main__":
    unittest.main()
