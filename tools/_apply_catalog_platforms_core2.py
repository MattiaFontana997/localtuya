from pathlib import Path

const_path = Path('custom_components/localtuya/const.py')
text = const_path.read_text()
start = text.index('PLATFORMS = [')
end = text.index(']\n', start) + 2
platform_block = '''PLATFORMS = [
    "alarm_control_panel",
    "binary_sensor",
    "button",
    "camera",
    "climate",
    "cover",
    "fan",
    "humidifier",
    "light",
    "lock",
    "number",
    "select",
    "sensor",
    "siren",
    "switch",
    "text",
    "time",
    "vacuum",
    "valve",
    "water_heater",
]'''
text = text[:start] + platform_block + text[end:]

anchor = '\n# number\n'
if anchor not in text:
    raise SystemExit('const anchor not found')
constants = r'''

# time
CONF_TIME_HOUR_DP = "time_hour_dp"
CONF_TIME_MINUTE_DP = "time_minute_dp"
CONF_TIME_SECOND_DP = "time_second_dp"
CONF_TIME_HMS_DP = "time_hms_dp"

# water heater
CONF_WATER_HEATER_CURRENT_TEMP_DP = "water_heater_current_temperature_dp"
CONF_WATER_HEATER_TARGET_TEMP_DP = "water_heater_target_temperature_dp"
CONF_WATER_HEATER_CURRENT_TEMP_SCALING = "water_heater_current_temperature_scaling"
CONF_WATER_HEATER_TARGET_TEMP_SCALING = "water_heater_target_temperature_scaling"
CONF_WATER_HEATER_TEMP_MIN = "water_heater_temperature_min"
CONF_WATER_HEATER_TEMP_MAX = "water_heater_temperature_max"
CONF_WATER_HEATER_TEMP_STEP = "water_heater_temperature_step"
CONF_WATER_HEATER_TEMP_UNIT = "water_heater_temperature_unit"
CONF_WATER_HEATER_TEMP_UNIT_DP = "water_heater_temperature_unit_dp"
CONF_WATER_HEATER_TEMP_UNIT_VALUES = "water_heater_temperature_unit_values"
CONF_WATER_HEATER_MIN_TEMP_DP = "water_heater_min_temperature_dp"
CONF_WATER_HEATER_MAX_TEMP_DP = "water_heater_max_temperature_dp"
CONF_WATER_HEATER_OPERATION_DP = "water_heater_operation_mode_dp"
CONF_WATER_HEATER_OPERATION_VALUES = "water_heater_operation_mode_values"
CONF_WATER_HEATER_ON_OPERATION = "water_heater_on_operation"
CONF_WATER_HEATER_OFF_OPERATION = "water_heater_off_operation"
CONF_WATER_HEATER_AWAY_DP = "water_heater_away_mode_dp"
CONF_WATER_HEATER_AWAY_ON = "water_heater_away_mode_on"
CONF_WATER_HEATER_AWAY_OFF = "water_heater_away_mode_off"

# alarm control panel
CONF_ALARM_STATE_DP = "alarm_state_dp"
CONF_ALARM_STATE_VALUES = "alarm_state_values"
CONF_ALARM_TRIGGER_DP = "alarm_trigger_dp"
CONF_ALARM_TRIGGER_ON = "alarm_trigger_on"

# siren
CONF_SIREN_SWITCH_DP = "siren_switch_dp"
CONF_SIREN_SWITCH_ON = "siren_switch_on"
CONF_SIREN_SWITCH_OFF = "siren_switch_off"
CONF_SIREN_TONE_DP = "siren_tone_dp"
CONF_SIREN_TONE_VALUES = "siren_tone_values"
CONF_SIREN_DEFAULT_TONE = "siren_default_tone"
CONF_SIREN_DURATION_DP = "siren_duration_dp"
CONF_SIREN_DURATION_SCALING = "siren_duration_scaling"
CONF_SIREN_VOLUME_DP = "siren_volume_dp"
CONF_SIREN_VOLUME_SCALING = "siren_volume_scaling"
CONF_SIREN_VOLUME_VALUES = "siren_volume_values"

# camera
CONF_CAMERA_SWITCH_DP = "camera_switch_dp"
CONF_CAMERA_SWITCH_ON = "camera_switch_on"
CONF_CAMERA_SWITCH_OFF = "camera_switch_off"
CONF_CAMERA_SNAPSHOT_DP = "camera_snapshot_dp"
CONF_CAMERA_SNAPSHOT_ENCODING = "camera_snapshot_encoding"
CONF_CAMERA_RECORD_DP = "camera_record_dp"
CONF_CAMERA_RECORD_ON = "camera_record_on"
CONF_CAMERA_RECORD_OFF = "camera_record_off"
CONF_CAMERA_MOTION_DP = "camera_motion_enable_dp"
CONF_CAMERA_MOTION_ON = "camera_motion_enable_on"
CONF_CAMERA_MOTION_OFF = "camera_motion_enable_off"
'''
text = text.replace(anchor, constants + anchor, 1)
const_path.write_text(text)

# Optional-DP pruning dependencies for both core batches.
device_catalog = Path('custom_components/localtuya/device_catalog.py')
dc = device_catalog.read_text()
needle = '        "current_humidity_dp": ("current_humidity_precision",),\n'
if needle not in dc:
    raise SystemExit('device catalog dependency anchor not found')
deps = needle + '''        "humidifier_switch_dp": ("humidifier_switch_on", "humidifier_switch_off"),
        "humidifier_mode_dp": ("humidifier_mode_values",),
        "humidifier_action_dp": ("humidifier_action_values",),
        "lock_state_dp": ("lock_state_values",),
        "lock_open_dp": ("lock_open_values", "lock_open_writable"),
        "lock_jammed_dp": ("lock_jammed_values",),
        "valve_switch_dp": ("valve_switch_on", "valve_switch_off"),
        "water_heater_temperature_unit_dp": ("water_heater_temperature_unit_values",),
        "water_heater_operation_mode_dp": (
            "water_heater_operation_mode_values",
            "water_heater_on_operation",
            "water_heater_off_operation",
        ),
        "water_heater_away_mode_dp": (
            "water_heater_away_mode_on", "water_heater_away_mode_off",
        ),
        "alarm_state_dp": ("alarm_state_values",),
        "alarm_trigger_dp": ("alarm_trigger_on",),
        "siren_switch_dp": ("siren_switch_on", "siren_switch_off"),
        "siren_tone_dp": ("siren_tone_values", "siren_default_tone"),
        "siren_duration_dp": ("siren_duration_scaling",),
        "siren_volume_dp": ("siren_volume_scaling", "siren_volume_values"),
        "camera_switch_dp": ("camera_switch_on", "camera_switch_off"),
        "camera_snapshot_dp": ("camera_snapshot_encoding",),
        "camera_record_dp": ("camera_record_on", "camera_record_off"),
        "camera_motion_enable_dp": (
            "camera_motion_enable_on", "camera_motion_enable_off",
        ),
'''
dc = dc.replace(needle, deps, 1)
device_catalog.write_text(dc)

Path('custom_components/localtuya/time.py').write_text(r'''"""Platform to locally control Tuya time datapoints."""

import logging
from datetime import time
from functools import partial

import voluptuous as vol
from homeassistant.components.time import DOMAIN, TimeEntity

from .common import LocalTuyaEntity, async_setup_entry
from .const import CONF_TIME_HMS_DP, CONF_TIME_HOUR_DP, CONF_TIME_MINUTE_DP, CONF_TIME_SECOND_DP

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_TIME_HOUR_DP): vol.In(dps),
        vol.Optional(CONF_TIME_MINUTE_DP): vol.In(dps),
        vol.Optional(CONF_TIME_SECOND_DP): vol.In(dps),
        vol.Optional(CONF_TIME_HMS_DP): vol.In(dps),
    }


def _parse_hms(value):
    if not isinstance(value, str) or not value:
        return None
    parts = value.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]), int(parts[1]), int(parts[2])
        if len(parts) == 2:
            return int(parts[0]), int(parts[1]), 0
        if len(parts) == 1:
            raw = parts[0]
            if len(raw) <= 2:
                return int(raw), 0, 0
            if len(raw) <= 4:
                return int(raw[:-2]), int(raw[-2:]), 0
            return int(raw[:-4]), int(raw[-4:-2]), int(raw[-2:])
    except ValueError:
        return None
    return None


class LocaltuyaTime(LocalTuyaEntity, TimeEntity):
    """Representation of a Tuya time entity."""

    @property
    def native_value(self):
        hours = minutes = seconds = None
        if self.has_config(CONF_TIME_HOUR_DP):
            hours = self.dps(self._config[CONF_TIME_HOUR_DP])
        if self.has_config(CONF_TIME_MINUTE_DP):
            minutes = self.dps(self._config[CONF_TIME_MINUTE_DP])
        if self.has_config(CONF_TIME_SECOND_DP):
            seconds = self.dps(self._config[CONF_TIME_SECOND_DP])
        if self.has_config(CONF_TIME_HMS_DP):
            parsed = _parse_hms(self.dps(self._config[CONF_TIME_HMS_DP]))
            if parsed is not None:
                hours, minutes, seconds = parsed
        if hours is None and minutes is None and seconds is None:
            return None
        try:
            total = (int(hours or 0) * 3600 + int(minutes or 0) * 60 + int(seconds or 0)) % 86400
        except (TypeError, ValueError):
            return None
        return time(total // 3600, (total % 3600) // 60, total % 60)

    async def async_set_value(self, value: time) -> None:
        settings = {}
        hours = value.hour
        minutes = value.minute
        seconds = value.second
        if self.has_config(CONF_TIME_HOUR_DP):
            settings[self._config[CONF_TIME_HOUR_DP]] = hours
        else:
            minutes += hours * 60
        if self.has_config(CONF_TIME_MINUTE_DP):
            settings[self._config[CONF_TIME_MINUTE_DP]] = minutes
        else:
            seconds += minutes * 60
        if self.has_config(CONF_TIME_SECOND_DP):
            settings[self._config[CONF_TIME_SECOND_DP]] = seconds
        if not settings and self.has_config(CONF_TIME_HMS_DP):
            settings[self._config[CONF_TIME_HMS_DP]] = value.strftime("%H:%M:%S")
        if not settings:
            raise NotImplementedError()
        await self._device.set_dps(settings)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaTime, flow_schema)
''')

Path('custom_components/localtuya/water_heater.py').write_text(r'''"""Platform to locally control Tuya water heaters."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.water_heater import DOMAIN, WaterHeaterEntity, WaterHeaterEntityFeature
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_WATER_HEATER_AWAY_DP,
    CONF_WATER_HEATER_AWAY_OFF,
    CONF_WATER_HEATER_AWAY_ON,
    CONF_WATER_HEATER_CURRENT_TEMP_DP,
    CONF_WATER_HEATER_CURRENT_TEMP_SCALING,
    CONF_WATER_HEATER_MAX_TEMP_DP,
    CONF_WATER_HEATER_MIN_TEMP_DP,
    CONF_WATER_HEATER_OFF_OPERATION,
    CONF_WATER_HEATER_ON_OPERATION,
    CONF_WATER_HEATER_OPERATION_DP,
    CONF_WATER_HEATER_OPERATION_VALUES,
    CONF_WATER_HEATER_TARGET_TEMP_DP,
    CONF_WATER_HEATER_TARGET_TEMP_SCALING,
    CONF_WATER_HEATER_TEMP_MAX,
    CONF_WATER_HEATER_TEMP_MIN,
    CONF_WATER_HEATER_TEMP_STEP,
    CONF_WATER_HEATER_TEMP_UNIT,
    CONF_WATER_HEATER_TEMP_UNIT_DP,
    CONF_WATER_HEATER_TEMP_UNIT_VALUES,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    return {
        vol.Optional(CONF_WATER_HEATER_CURRENT_TEMP_DP): vol.In(dps),
        vol.Optional(CONF_WATER_HEATER_TARGET_TEMP_DP): vol.In(dps),
        vol.Optional(CONF_WATER_HEATER_TEMP_UNIT_DP): vol.In(dps),
        vol.Optional(CONF_WATER_HEATER_MIN_TEMP_DP): vol.In(dps),
        vol.Optional(CONF_WATER_HEATER_MAX_TEMP_DP): vol.In(dps),
        vol.Optional(CONF_WATER_HEATER_OPERATION_DP): vol.In(dps),
        vol.Optional(CONF_WATER_HEATER_AWAY_DP): vol.In(dps),
    }


def _decode(values, raw):
    if isinstance(values, dict):
        for friendly, configured_raw in values.items():
            if raw == configured_raw:
                return friendly
    return raw


def _scaled(raw, factor):
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return float(raw) * float(factor)


def _raw_temperature(value, factor):
    raw = float(value) / float(factor)
    rounded = round(raw, 10)
    return int(rounded) if float(rounded).is_integer() else rounded


class LocaltuyaWaterHeater(LocalTuyaEntity, WaterHeaterEntity):
    """Representation of a Tuya water heater."""

    def __init__(self, device, config_entry, dp_id, **kwargs):
        super().__init__(device, config_entry, dp_id, _LOGGER, **kwargs)
        self._current_scale = float(self._config.get(CONF_WATER_HEATER_CURRENT_TEMP_SCALING, 1.0))
        self._target_scale = float(self._config.get(CONF_WATER_HEATER_TARGET_TEMP_SCALING, 1.0))
        self._operation_values = self._config.get(CONF_WATER_HEATER_OPERATION_VALUES, {})
        self._unit_values = self._config.get(CONF_WATER_HEATER_TEMP_UNIT_VALUES, {})
        support = WaterHeaterEntityFeature(0)
        if self.has_config(CONF_WATER_HEATER_TARGET_TEMP_DP):
            support |= WaterHeaterEntityFeature.TARGET_TEMPERATURE
        if self.has_config(CONF_WATER_HEATER_OPERATION_DP) and self._operation_values:
            support |= WaterHeaterEntityFeature.OPERATION_MODE
        if self.has_config(CONF_WATER_HEATER_AWAY_DP) or "away" in self._operation_values:
            support |= WaterHeaterEntityFeature.AWAY_MODE
        if self.has_config(CONF_WATER_HEATER_ON_OPERATION) and self.has_config(CONF_WATER_HEATER_OFF_OPERATION):
            support |= WaterHeaterEntityFeature.ON_OFF
        self._attr_supported_features = support

    @property
    def temperature_unit(self):
        unit = self._config.get(CONF_WATER_HEATER_TEMP_UNIT)
        if self.has_config(CONF_WATER_HEATER_TEMP_UNIT_DP):
            unit = _decode(self._unit_values, self.dps(self._config[CONF_WATER_HEATER_TEMP_UNIT_DP]))
        normalized = str(unit or "C").strip().replace("°", "").upper()
        if normalized in {"F", "FAHRENHEIT"}:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self):
        if not self.has_config(CONF_WATER_HEATER_CURRENT_TEMP_DP):
            return None
        return _scaled(self.dps(self._config[CONF_WATER_HEATER_CURRENT_TEMP_DP]), self._current_scale)

    @property
    def target_temperature(self):
        if not self.has_config(CONF_WATER_HEATER_TARGET_TEMP_DP):
            return None
        return _scaled(self.dps(self._config[CONF_WATER_HEATER_TARGET_TEMP_DP]), self._target_scale)

    @property
    def target_temperature_step(self):
        return float(self._config.get(CONF_WATER_HEATER_TEMP_STEP, 1.0))

    @property
    def min_temp(self):
        if self.has_config(CONF_WATER_HEATER_MIN_TEMP_DP):
            value = _scaled(self.dps(self._config[CONF_WATER_HEATER_MIN_TEMP_DP]), self._target_scale)
            if value is not None:
                return value
        return float(self._config.get(CONF_WATER_HEATER_TEMP_MIN, 0.0))

    @property
    def max_temp(self):
        if self.has_config(CONF_WATER_HEATER_MAX_TEMP_DP):
            value = _scaled(self.dps(self._config[CONF_WATER_HEATER_MAX_TEMP_DP]), self._target_scale)
            if value is not None:
                return value
        return float(self._config.get(CONF_WATER_HEATER_TEMP_MAX, 100.0))

    @property
    def current_operation(self):
        if not self.has_config(CONF_WATER_HEATER_OPERATION_DP):
            return None
        mode = _decode(self._operation_values, self.dps(self._config[CONF_WATER_HEATER_OPERATION_DP]))
        return "eco" if mode == "away" else mode

    @property
    def operation_list(self):
        return [mode for mode in self._operation_values if mode != "away"]

    @property
    def is_away_mode_on(self):
        if self.has_config(CONF_WATER_HEATER_AWAY_DP):
            return self.dps(self._config[CONF_WATER_HEATER_AWAY_DP]) == self._config.get(CONF_WATER_HEATER_AWAY_ON, True)
        if self.has_config(CONF_WATER_HEATER_OPERATION_DP):
            return _decode(self._operation_values, self.dps(self._config[CONF_WATER_HEATER_OPERATION_DP])) == "away"
        return None

    async def async_set_temperature(self, **kwargs):
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            if not self.has_config(CONF_WATER_HEATER_TARGET_TEMP_DP):
                raise NotImplementedError()
            await self._device.set_dp(
                _raw_temperature(kwargs[ATTR_TEMPERATURE], self._target_scale),
                self._config[CONF_WATER_HEATER_TARGET_TEMP_DP],
            )
        operation = kwargs.get("operation_mode")
        if operation is not None:
            await self.async_set_operation_mode(operation)

    async def async_set_operation_mode(self, operation_mode):
        if not self.has_config(CONF_WATER_HEATER_OPERATION_DP) or operation_mode not in self._operation_values:
            raise NotImplementedError()
        await self._device.set_dp(self._operation_values[operation_mode], self._config[CONF_WATER_HEATER_OPERATION_DP])

    async def async_turn_on(self):
        operation = self._config.get(CONF_WATER_HEATER_ON_OPERATION)
        if operation is None:
            raise NotImplementedError()
        await self.async_set_operation_mode(operation)

    async def async_turn_off(self):
        operation = self._config.get(CONF_WATER_HEATER_OFF_OPERATION)
        if operation is None:
            raise NotImplementedError()
        await self.async_set_operation_mode(operation)

    async def async_turn_away_mode_on(self):
        if self.has_config(CONF_WATER_HEATER_AWAY_DP):
            await self._device.set_dp(self._config.get(CONF_WATER_HEATER_AWAY_ON, True), self._config[CONF_WATER_HEATER_AWAY_DP])
            return
        if "away" in self._operation_values:
            await self.async_set_operation_mode("away")
            return
        raise NotImplementedError()

    async def async_turn_away_mode_off(self):
        if self.has_config(CONF_WATER_HEATER_AWAY_DP):
            await self._device.set_dp(self._config.get(CONF_WATER_HEATER_AWAY_OFF, False), self._config[CONF_WATER_HEATER_AWAY_DP])
            return
        modes = [mode for mode in self._operation_values if mode not in {"away", self._config.get(CONF_WATER_HEATER_OFF_OPERATION)}]
        if modes:
            await self.async_set_operation_mode(modes[0])
            return
        raise NotImplementedError()


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaWaterHeater, flow_schema)
''')

Path('custom_components/localtuya/alarm_control_panel.py').write_text(r'''"""Platform to locally control Tuya alarm control panels."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.alarm_control_panel import DOMAIN, AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelEntityFeature as Feature, AlarmControlPanelState

from .common import LocalTuyaEntity, async_setup_entry
from .const import CONF_ALARM_STATE_DP, CONF_ALARM_STATE_VALUES, CONF_ALARM_TRIGGER_DP, CONF_ALARM_TRIGGER_ON

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    return {
        vol.Optional(CONF_ALARM_STATE_DP): vol.In(dps),
        vol.Optional(CONF_ALARM_TRIGGER_DP): vol.In(dps),
    }


def _decode(values, raw):
    for friendly, configured_raw in (values or {}).items():
        if raw == configured_raw:
            return friendly
    return None


class LocaltuyaAlarmControlPanel(LocalTuyaEntity, AlarmControlPanelEntity):
    def __init__(self, device, config_entry, dp_id, **kwargs):
        super().__init__(device, config_entry, dp_id, _LOGGER, **kwargs)
        self._state_values = self._config.get(CONF_ALARM_STATE_VALUES, {})
        support = Feature(0)
        states = set(self._state_values)
        if AlarmControlPanelState.ARMED_HOME in states or AlarmControlPanelState.ARMED_HOME.value in states:
            support |= Feature.ARM_HOME
        if AlarmControlPanelState.ARMED_AWAY in states or AlarmControlPanelState.ARMED_AWAY.value in states:
            support |= Feature.ARM_AWAY
        if AlarmControlPanelState.ARMED_NIGHT in states or AlarmControlPanelState.ARMED_NIGHT.value in states:
            support |= Feature.ARM_NIGHT
        if AlarmControlPanelState.ARMED_VACATION in states or AlarmControlPanelState.ARMED_VACATION.value in states:
            support |= Feature.ARM_VACATION
        if AlarmControlPanelState.ARMED_CUSTOM_BYPASS in states or AlarmControlPanelState.ARMED_CUSTOM_BYPASS.value in states:
            support |= Feature.ARM_CUSTOM_BYPASS
        if self.has_config(CONF_ALARM_TRIGGER_DP) or AlarmControlPanelState.TRIGGERED.value in states:
            support |= Feature.TRIGGER
        self._attr_supported_features = support
        self._attr_code_format = None
        self._attr_code_arm_required = False

    @property
    def alarm_state(self):
        if self.has_config(CONF_ALARM_TRIGGER_DP):
            if self.dps(self._config[CONF_ALARM_TRIGGER_DP]) == self._config.get(CONF_ALARM_TRIGGER_ON, True):
                return AlarmControlPanelState.TRIGGERED
        dp_id = self._config.get(CONF_ALARM_STATE_DP, self._dp_id)
        friendly = _decode(self._state_values, self.dps(dp_id))
        if friendly is None:
            return None
        try:
            return AlarmControlPanelState(friendly)
        except ValueError:
            return None

    async def _send(self, state):
        friendly = state.value if hasattr(state, "value") else str(state)
        if friendly not in self._state_values:
            raise NotImplementedError()
        await self._device.set_dp(self._state_values[friendly], self._config.get(CONF_ALARM_STATE_DP, self._dp_id))

    async def async_alarm_disarm(self, code=None):
        await self._send(AlarmControlPanelState.DISARMED)

    async def async_alarm_arm_home(self, code=None):
        await self._send(AlarmControlPanelState.ARMED_HOME)

    async def async_alarm_arm_away(self, code=None):
        await self._send(AlarmControlPanelState.ARMED_AWAY)

    async def async_alarm_arm_night(self, code=None):
        await self._send(AlarmControlPanelState.ARMED_NIGHT)

    async def async_alarm_arm_vacation(self, code=None):
        await self._send(AlarmControlPanelState.ARMED_VACATION)

    async def async_alarm_arm_custom_bypass(self, code=None):
        await self._send(AlarmControlPanelState.ARMED_CUSTOM_BYPASS)

    async def async_alarm_trigger(self, code=None):
        if self.has_config(CONF_ALARM_TRIGGER_DP):
            await self._device.set_dp(self._config.get(CONF_ALARM_TRIGGER_ON, True), self._config[CONF_ALARM_TRIGGER_DP])
            return
        await self._send(AlarmControlPanelState.TRIGGERED)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaAlarmControlPanel, flow_schema)
''')

Path('custom_components/localtuya/siren.py').write_text(r'''"""Platform to locally control Tuya sirens."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.siren import DOMAIN, SirenEntity, SirenEntityFeature
from homeassistant.components.siren.const import ATTR_DURATION, ATTR_TONE, ATTR_VOLUME_LEVEL

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_SIREN_DEFAULT_TONE,
    CONF_SIREN_DURATION_DP,
    CONF_SIREN_DURATION_SCALING,
    CONF_SIREN_SWITCH_DP,
    CONF_SIREN_SWITCH_OFF,
    CONF_SIREN_SWITCH_ON,
    CONF_SIREN_TONE_DP,
    CONF_SIREN_TONE_VALUES,
    CONF_SIREN_VOLUME_DP,
    CONF_SIREN_VOLUME_SCALING,
    CONF_SIREN_VOLUME_VALUES,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    return {
        vol.Optional(CONF_SIREN_SWITCH_DP): vol.In(dps),
        vol.Optional(CONF_SIREN_TONE_DP): vol.In(dps),
        vol.Optional(CONF_SIREN_DURATION_DP): vol.In(dps),
        vol.Optional(CONF_SIREN_VOLUME_DP): vol.In(dps),
    }


def _decode(values, raw):
    for friendly, configured_raw in (values or {}).items():
        if raw == configured_raw:
            return friendly
    return raw


class LocaltuyaSiren(LocalTuyaEntity, SirenEntity):
    def __init__(self, device, config_entry, dp_id, **kwargs):
        super().__init__(device, config_entry, dp_id, _LOGGER, **kwargs)
        self._tone_values = self._config.get(CONF_SIREN_TONE_VALUES, {})
        self._volume_values = self._config.get(CONF_SIREN_VOLUME_VALUES, {})
        support = SirenEntityFeature(0)
        if self.has_config(CONF_SIREN_TONE_DP):
            support |= SirenEntityFeature.TONES | SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
            self._attr_available_tones = [tone for tone in self._tone_values if tone != "off"]
        if self.has_config(CONF_SIREN_VOLUME_DP):
            support |= SirenEntityFeature.VOLUME_SET
        if self.has_config(CONF_SIREN_DURATION_DP):
            support |= SirenEntityFeature.DURATION
        if self.has_config(CONF_SIREN_SWITCH_DP):
            support |= SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
        self._attr_supported_features = support

    @property
    def is_on(self):
        if self.has_config(CONF_SIREN_SWITCH_DP):
            raw = self.dps(self._config[CONF_SIREN_SWITCH_DP])
            if raw == self._config.get(CONF_SIREN_SWITCH_ON, True):
                return True
            if raw == self._config.get(CONF_SIREN_SWITCH_OFF, False):
                return False
            return None
        if self.has_config(CONF_SIREN_TONE_DP):
            return _decode(self._tone_values, self.dps(self._config[CONF_SIREN_TONE_DP])) != "off"
        return None

    def _volume_raw(self, volume):
        if self._volume_values:
            choices = [(float(level), raw) for level, raw in self._volume_values.items()]
            return min(choices, key=lambda item: abs(item[0] - float(volume)))[1]
        factor = float(self._config.get(CONF_SIREN_VOLUME_SCALING, 1.0))
        raw = float(volume) / factor
        raw = round(raw, 10)
        return int(raw) if float(raw).is_integer() else raw

    async def async_turn_on(self, **kwargs):
        settings = {}
        tone = kwargs.get(ATTR_TONE)
        if self.has_config(CONF_SIREN_TONE_DP):
            if tone is None and not self.has_config(CONF_SIREN_SWITCH_DP):
                current = _decode(self._tone_values, self.dps(self._config[CONF_SIREN_TONE_DP]))
                if current == "off" or current not in self._tone_values:
                    tone = self._config.get(CONF_SIREN_DEFAULT_TONE)
            if tone is not None:
                if tone not in self._tone_values:
                    raise ValueError(f"Unsupported siren tone {tone!r}")
                settings[self._config[CONF_SIREN_TONE_DP]] = self._tone_values[tone]
        if kwargs.get(ATTR_DURATION) is not None and self.has_config(CONF_SIREN_DURATION_DP):
            factor = float(self._config.get(CONF_SIREN_DURATION_SCALING, 1.0))
            raw = float(kwargs[ATTR_DURATION]) / factor
            settings[self._config[CONF_SIREN_DURATION_DP]] = int(raw) if raw.is_integer() else raw
        if kwargs.get(ATTR_VOLUME_LEVEL) is not None and self.has_config(CONF_SIREN_VOLUME_DP):
            settings[self._config[CONF_SIREN_VOLUME_DP]] = self._volume_raw(kwargs[ATTR_VOLUME_LEVEL])
        if self.has_config(CONF_SIREN_SWITCH_DP) and self.is_on is not True:
            settings[self._config[CONF_SIREN_SWITCH_DP]] = self._config.get(CONF_SIREN_SWITCH_ON, True)
        if not settings:
            raise NotImplementedError()
        await self._device.set_dps(settings)

    async def async_turn_off(self):
        if self.has_config(CONF_SIREN_SWITCH_DP):
            await self._device.set_dp(self._config.get(CONF_SIREN_SWITCH_OFF, False), self._config[CONF_SIREN_SWITCH_DP])
            return
        if self.has_config(CONF_SIREN_TONE_DP) and "off" in self._tone_values:
            await self._device.set_dp(self._tone_values["off"], self._config[CONF_SIREN_TONE_DP])
            return
        raise NotImplementedError()


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaSiren, flow_schema)
''')

Path('custom_components/localtuya/camera.py').write_text(r'''"""Platform to expose DP-driven Tuya cameras."""

import base64
import binascii
import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.camera import DOMAIN, Camera as CameraEntity, CameraEntityFeature

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_CAMERA_MOTION_DP,
    CONF_CAMERA_MOTION_OFF,
    CONF_CAMERA_MOTION_ON,
    CONF_CAMERA_RECORD_DP,
    CONF_CAMERA_RECORD_OFF,
    CONF_CAMERA_RECORD_ON,
    CONF_CAMERA_SNAPSHOT_DP,
    CONF_CAMERA_SNAPSHOT_ENCODING,
    CONF_CAMERA_SWITCH_DP,
    CONF_CAMERA_SWITCH_OFF,
    CONF_CAMERA_SWITCH_ON,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    return {
        vol.Optional(CONF_CAMERA_SWITCH_DP): vol.In(dps),
        vol.Optional(CONF_CAMERA_SNAPSHOT_DP): vol.In(dps),
        vol.Optional(CONF_CAMERA_RECORD_DP): vol.In(dps),
        vol.Optional(CONF_CAMERA_MOTION_DP): vol.In(dps),
    }


def _decode_snapshot(raw, encoding):
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        if encoding == "base64":
            return base64.b64decode(raw, validate=True)
        if encoding == "hex":
            return bytes.fromhex(raw)
        return raw.encode()
    except (ValueError, binascii.Error):
        return None


class LocaltuyaCamera(LocalTuyaEntity, CameraEntity):
    def __init__(self, device, config_entry, dp_id, **kwargs):
        CameraEntity.__init__(self)
        LocalTuyaEntity.__init__(self, device, config_entry, dp_id, _LOGGER, **kwargs)
        if self.has_config(CONF_CAMERA_SWITCH_DP):
            self._attr_supported_features |= CameraEntityFeature.ON_OFF

    @property
    def is_on(self):
        if not self.has_config(CONF_CAMERA_SWITCH_DP):
            return None
        raw = self.dps(self._config[CONF_CAMERA_SWITCH_DP])
        if raw == self._config.get(CONF_CAMERA_SWITCH_ON, True):
            return True
        if raw == self._config.get(CONF_CAMERA_SWITCH_OFF, False):
            return False
        return None

    @property
    def is_recording(self):
        if not self.has_config(CONF_CAMERA_RECORD_DP):
            return None
        raw = self.dps(self._config[CONF_CAMERA_RECORD_DP])
        if raw == self._config.get(CONF_CAMERA_RECORD_ON, True):
            return True
        if raw == self._config.get(CONF_CAMERA_RECORD_OFF, False):
            return False
        return None

    @property
    def motion_detection_enabled(self):
        if not self.has_config(CONF_CAMERA_MOTION_DP):
            return None
        raw = self.dps(self._config[CONF_CAMERA_MOTION_DP])
        if raw == self._config.get(CONF_CAMERA_MOTION_ON, True):
            return True
        if raw == self._config.get(CONF_CAMERA_MOTION_OFF, False):
            return False
        return None

    async def async_camera_image(self, width=None, height=None):
        if not self.has_config(CONF_CAMERA_SNAPSHOT_DP):
            return None
        return _decode_snapshot(
            self.dps(self._config[CONF_CAMERA_SNAPSHOT_DP]),
            self._config.get(CONF_CAMERA_SNAPSHOT_ENCODING, "base64"),
        )

    async def async_turn_on(self):
        if not self.has_config(CONF_CAMERA_SWITCH_DP):
            raise NotImplementedError()
        await self._device.set_dp(self._config.get(CONF_CAMERA_SWITCH_ON, True), self._config[CONF_CAMERA_SWITCH_DP])

    async def async_turn_off(self):
        if not self.has_config(CONF_CAMERA_SWITCH_DP):
            raise NotImplementedError()
        await self._device.set_dp(self._config.get(CONF_CAMERA_SWITCH_OFF, False), self._config[CONF_CAMERA_SWITCH_DP])

    async def async_enable_motion_detection(self):
        if not self.has_config(CONF_CAMERA_MOTION_DP):
            raise NotImplementedError()
        await self._device.set_dp(self._config.get(CONF_CAMERA_MOTION_ON, True), self._config[CONF_CAMERA_MOTION_DP])

    async def async_disable_motion_detection(self):
        if not self.has_config(CONF_CAMERA_MOTION_DP):
            raise NotImplementedError()
        await self._device.set_dp(self._config.get(CONF_CAMERA_MOTION_OFF, False), self._config[CONF_CAMERA_MOTION_DP])


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaCamera, flow_schema)
''')

Path('tests/test_catalog_platforms_core2.py').write_text(r'''"""Regression tests for the second catalog platform runtime batch."""

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
''')
