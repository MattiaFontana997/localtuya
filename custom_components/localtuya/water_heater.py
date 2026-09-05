"""Platform to locally control Tuya water heaters."""

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
