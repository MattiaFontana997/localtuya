"""Regression tests for catalog-driven Batch B platform runtimes."""

from datetime import time
import unittest
from unittest.mock import AsyncMock

from homeassistant.components.alarm_control_panel.const import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.components.siren.const import ATTR_DURATION, ATTR_TONE, ATTR_VOLUME_LEVEL
from homeassistant.components.water_heater import WaterHeaterEntityFeature
from homeassistant.const import ATTR_TEMPERATURE

from custom_components.localtuya.alarm_control_panel import LocaltuyaAlarmControlPanel
from custom_components.localtuya.const import (
    CONF_ALARM_STATE_DP,
    CONF_ALARM_STATE_VALUES,
    CONF_ALARM_TRIGGER_DP,
    CONF_ALARM_TRIGGER_OFF,
    CONF_ALARM_TRIGGER_ON,
    CONF_SIREN_DEFAULT_TONE,
    CONF_SIREN_DURATION_DP,
    CONF_SIREN_SWITCH_DP,
    CONF_SIREN_SWITCH_OFF,
    CONF_SIREN_SWITCH_ON,
    CONF_SIREN_TONE_DP,
    CONF_SIREN_TONE_VALUES,
    CONF_SIREN_VOLUME_DP,
    CONF_SIREN_VOLUME_VALUES,
    CONF_TIME_HMS_DP,
    CONF_TIME_HMS_FORMAT,
    CONF_TIME_HOUR_DP,
    CONF_TIME_MINUTE_DP,
    CONF_WATER_HEATER_AWAY_MODE,
    CONF_WATER_HEATER_CURRENT_TEMPERATURE_DP,
    CONF_WATER_HEATER_MODE_DP,
    CONF_WATER_HEATER_MODE_VALUES,
    CONF_WATER_HEATER_POWER_DP,
    CONF_WATER_HEATER_POWER_OFF,
    CONF_WATER_HEATER_POWER_ON,
    CONF_WATER_HEATER_TARGET_TEMPERATURE_DP,
    CONF_WATER_HEATER_TEMPERATURE_SCALING,
)
from custom_components.localtuya.device_catalog import validate_catalog
from custom_components.localtuya.siren import LocaltuyaSiren
from custom_components.localtuya.time import LocaltuyaTime
from custom_components.localtuya.water_heater import LocaltuyaWaterHeater


class _Device:
    def __init__(self):
        self.set_dp = AsyncMock()
        self.set_dps = AsyncMock()
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


class BatchBPlatformRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_time_combined_and_split_round_trip(self):
        combined = _entity(
            LocaltuyaTime,
            {"id": 1, CONF_TIME_HMS_DP: 5, CONF_TIME_HMS_FORMAT: "compact_hms"},
            {5: "073045"},
        )
        combined._hms_format = "compact_hms"
        self.assertEqual(combined.native_value, time(7, 30, 45))
        await combined.async_set_value(time(19, 2, 3))
        combined._device.set_dp.assert_awaited_once_with("190203", 5)

        split = _entity(
            LocaltuyaTime,
            {"id": 2, CONF_TIME_HOUR_DP: 2, CONF_TIME_MINUTE_DP: 3},
            {2: 12, 3: 34},
        )
        self.assertEqual(split.native_value, time(12, 34))
        await split.async_set_value(time(8, 9, 10))
        split._device.set_dps.assert_awaited_once_with({2: 8, 3: 9})

    async def test_water_heater_scaling_modes_and_power(self):
        config = {
            "id": 10,
            CONF_WATER_HEATER_POWER_DP: 1,
            CONF_WATER_HEATER_POWER_ON: "on",
            CONF_WATER_HEATER_POWER_OFF: "off",
            CONF_WATER_HEATER_CURRENT_TEMPERATURE_DP: 2,
            CONF_WATER_HEATER_TARGET_TEMPERATURE_DP: 3,
            CONF_WATER_HEATER_TEMPERATURE_SCALING: 0.1,
            CONF_WATER_HEATER_MODE_DP: 4,
            CONF_WATER_HEATER_MODE_VALUES: {"eco": "E", "boost": "B", "away": "A"},
            CONF_WATER_HEATER_AWAY_MODE: "away",
        }
        heater = _entity(LocaltuyaWaterHeater, config, {1: "on", 2: 423, 3: 550, 4: "B"})
        heater._scaling = 0.1
        heater._temp_min = 5.0
        heater._temp_max = 90.0
        heater._temp_step = 1.0
        heater._power_on = "on"
        heater._power_off = "off"
        heater._mode_values = config[CONF_WATER_HEATER_MODE_VALUES]
        heater._unit_values = {}
        heater._away_on = True
        heater._away_off = False
        heater._away_mode = "away"
        heater._default_mode = "eco"
        self.assertEqual(heater.current_temperature, 42.3)
        self.assertEqual(heater.target_temperature, 55.0)
        self.assertEqual(heater.current_operation, "boost")
        self.assertEqual(heater.operation_list, ["eco", "boost"])
        await heater.async_set_temperature(**{ATTR_TEMPERATURE: 60})
        heater._device.set_dp.assert_awaited_once_with(600, 3)
        heater._device.set_dp.reset_mock()
        await heater.async_turn_on()
        heater._device.set_dp.assert_awaited_once_with("on", 1)

    async def test_siren_uses_exact_catalog_values(self):
        config = {
            "id": 7,
            CONF_SIREN_SWITCH_DP: 1,
            CONF_SIREN_SWITCH_ON: "ON",
            CONF_SIREN_SWITCH_OFF: "OFF",
            CONF_SIREN_TONE_DP: 2,
            CONF_SIREN_TONE_VALUES: {"off": "STOP", "alarm": "A", "chime": "C"},
            CONF_SIREN_DEFAULT_TONE: "alarm",
            CONF_SIREN_DURATION_DP: 3,
            CONF_SIREN_VOLUME_DP: 4,
            CONF_SIREN_VOLUME_VALUES: {"0.0": "LOW", "0.5": "MID", "1.0": "HIGH"},
        }
        siren = _entity(LocaltuyaSiren, config, {1: "OFF", 2: "STOP"})
        siren._switch_on = "ON"
        siren._switch_off = "OFF"
        siren._tone_values = config[CONF_SIREN_TONE_VALUES]
        siren._default_tone = "alarm"
        siren._duration_scaling = 1.0
        siren._volume_min = 0.0
        siren._volume_max = 100.0
        siren._volume_values = {0.0: "LOW", 0.5: "MID", 1.0: "HIGH"}
        await siren.async_turn_on(
            **{ATTR_TONE: "alarm", ATTR_DURATION: 7, ATTR_VOLUME_LEVEL: 0.6}
        )
        siren._device.set_dps.assert_awaited_once_with(
            {2: "A", 3: 7, 4: "MID", 1: "ON"}
        )

    async def test_alarm_state_features_and_exact_commands(self):
        values = {
            "disarmed": "D",
            "armed_home": "H",
            "armed_away": "A",
            "armed_night": "N",
            "triggered": "T",
        }
        config = {
            "id": 9,
            CONF_ALARM_STATE_DP: 9,
            CONF_ALARM_STATE_VALUES: values,
            CONF_ALARM_TRIGGER_DP: 10,
            CONF_ALARM_TRIGGER_ON: 1,
            CONF_ALARM_TRIGGER_OFF: 0,
        }
        alarm = _entity(LocaltuyaAlarmControlPanel, config, {9: "A", 10: 0})
        alarm._state_values = values
        alarm._trigger_on = 1
        alarm._trigger_off = 0
        self.assertEqual(alarm.alarm_state, AlarmControlPanelState.ARMED_AWAY)
        features = (
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_NIGHT
            | AlarmControlPanelEntityFeature.TRIGGER
        )
        inferred = AlarmControlPanelEntityFeature(0)
        for key, feature in {
            "armed_home": AlarmControlPanelEntityFeature.ARM_HOME,
            "armed_away": AlarmControlPanelEntityFeature.ARM_AWAY,
            "armed_night": AlarmControlPanelEntityFeature.ARM_NIGHT,
        }.items():
            if key in values:
                inferred |= feature
        if CONF_ALARM_TRIGGER_DP in config:
            inferred |= AlarmControlPanelEntityFeature.TRIGGER
        self.assertEqual(inferred, features)
        await alarm.async_alarm_arm_home()
        alarm._device.set_dp.assert_awaited_once_with("H", 9)
        alarm._device.set_dp.reset_mock()
        await alarm.async_alarm_trigger()
        alarm._device.set_dp.assert_awaited_once_with(1, 10)

    def test_catalog_accepts_batch_a_and_b_platforms(self):
        platforms = [
            "button",
            "text",
            "valve",
            "humidifier",
            "lock",
            "time",
            "water_heater",
            "siren",
            "alarm_control_panel",
        ]
        payload = {
            "schema_version": 2,
            "mappings": [
                {
                    "id": "batch-a-b-platforms",
                    "match": {
                        "product_ids": ["example-product"],
                        "required_dps": list(range(1, len(platforms) + 1)),
                        "optional_dps": [],
                    },
                    "entities": [
                        {"platform": platform, "config": {"id": index}}
                        for index, platform in enumerate(platforms, 1)
                    ],
                }
            ],
        }
        validated = validate_catalog(payload)
        self.assertEqual(len(validated["mappings"]), 1)
        self.assertEqual(
            {entity["platform"] for entity in validated["mappings"][0]["entities"]},
            set(platforms),
        )


if __name__ == "__main__":
    unittest.main()
