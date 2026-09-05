"""Regression tests for the second catalog platform runtime batch."""

import base64
import unittest
from datetime import time
from unittest.mock import AsyncMock

from custom_components.localtuya.alarm_control_panel import LocaltuyaAlarmControlPanel
from custom_components.localtuya.camera import LocaltuyaCamera, _decode_snapshot
from custom_components.localtuya.const import *
from custom_components.localtuya.siren import LocaltuyaSiren
from custom_components.localtuya.time import LocaltuyaTime, _parse_hms
from custom_components.localtuya.water_heater import LocaltuyaWaterHeater


class _Device:
    def __init__(self):
        self.set_dp = AsyncMock()
        self.set_dps = AsyncMock()
        self.is_connecting = False


def entity(cls, config, state):
    obj = object.__new__(cls)
    obj._config = config
    obj._dp_id = config["id"]
    obj._device = _Device()
    obj.has_config = lambda key: key in config and config[key] is not None
    obj.dps = lambda dp: state.get(dp)
    obj.warning = lambda *args, **kwargs: None
    return obj


class Core2RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def test_parse_hms_forms(self):
        self.assertEqual(_parse_hms("12:34:56"), (12, 34, 56))
        self.assertEqual(_parse_hms("1234"), (12, 34, 0))
        self.assertEqual(_parse_hms("123456"), (12, 34, 56))

    async def test_time_collapses_missing_hour_into_minutes(self):
        obj = entity(LocaltuyaTime, {"id": 2, CONF_TIME_MINUTE_DP: 2, CONF_TIME_SECOND_DP: 3}, {2: 90, 3: 5})
        self.assertEqual(obj.native_value, time(1, 30, 5))
        await obj.async_set_value(time(2, 10, 7))
        obj._device.set_dps.assert_awaited_once_with({2: 130, 3: 7})

    async def test_water_heater_exact_mode_and_scaling(self):
        config = {
            "id": 1,
            CONF_WATER_HEATER_CURRENT_TEMP_DP: 2,
            CONF_WATER_HEATER_CURRENT_TEMP_SCALING: 0.1,
            CONF_WATER_HEATER_TARGET_TEMP_DP: 3,
            CONF_WATER_HEATER_TARGET_TEMP_SCALING: 0.1,
            CONF_WATER_HEATER_OPERATION_DP: 1,
            CONF_WATER_HEATER_OPERATION_VALUES: {"off": False, "electric": True},
            CONF_WATER_HEATER_ON_OPERATION: "electric",
            CONF_WATER_HEATER_OFF_OPERATION: "off",
            CONF_WATER_HEATER_TEMP_MIN: 30,
            CONF_WATER_HEATER_TEMP_MAX: 90,
            CONF_WATER_HEATER_TEMP_STEP: 0.5,
        }
        obj = entity(LocaltuyaWaterHeater, config, {1: True, 2: 455, 3: 600})
        obj._current_scale = 0.1
        obj._target_scale = 0.1
        obj._operation_values = config[CONF_WATER_HEATER_OPERATION_VALUES]
        obj._unit_values = {}
        self.assertEqual(obj.current_temperature, 45.5)
        self.assertEqual(obj.target_temperature, 60.0)
        self.assertEqual(obj.current_operation, "electric")
        await obj.async_set_temperature(temperature=65)
        obj._device.set_dp.assert_awaited_once_with(650, 3)

    async def test_alarm_maps_exact_raw_state(self):
        from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
        config = {"id": 1, CONF_ALARM_STATE_DP: 1, CONF_ALARM_STATE_VALUES: {"disarmed": "D", "armed_away": "A"}}
        obj = entity(LocaltuyaAlarmControlPanel, config, {1: "A"})
        obj._state_values = config[CONF_ALARM_STATE_VALUES]
        self.assertEqual(obj.alarm_state, AlarmControlPanelState.ARMED_AWAY)
        await obj.async_alarm_disarm()
        obj._device.set_dp.assert_awaited_once_with("D", 1)

    async def test_siren_turn_on_sets_tone_volume_and_switch_atomically(self):
        config = {
            "id": 1,
            CONF_SIREN_SWITCH_DP: 1, CONF_SIREN_SWITCH_ON: "on", CONF_SIREN_SWITCH_OFF: "off",
            CONF_SIREN_TONE_DP: 2, CONF_SIREN_TONE_VALUES: {"off": "0", "alarm": "1"},
            CONF_SIREN_VOLUME_DP: 3, CONF_SIREN_VOLUME_VALUES: {"0.25": "low", "1.0": "high"},
        }
        obj = entity(LocaltuyaSiren, config, {1: "off", 2: "0"})
        obj._tone_values = config[CONF_SIREN_TONE_VALUES]
        obj._volume_values = config[CONF_SIREN_VOLUME_VALUES]
        await obj.async_turn_on(tone="alarm", volume_level=0.9)
        obj._device.set_dps.assert_awaited_once_with({2: "1", 3: "high", 1: "on"})

    def test_camera_snapshot_decodes_base64(self):
        payload = b"jpeg-bytes"
        self.assertEqual(_decode_snapshot(base64.b64encode(payload).decode(), "base64"), payload)

    async def test_camera_motion_uses_exact_raw_values(self):
        config = {"id": 1, CONF_CAMERA_MOTION_DP: 4, CONF_CAMERA_MOTION_ON: "enable", CONF_CAMERA_MOTION_OFF: "disable"}
        obj = entity(LocaltuyaCamera, config, {4: "disable"})
        await obj.async_enable_motion_detection()
        obj._device.set_dp.assert_awaited_once_with("enable", 4)


if __name__ == "__main__":
    unittest.main()
