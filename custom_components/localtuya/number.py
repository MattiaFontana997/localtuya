"""Platform to present any Tuya DP as a number."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.number import DOMAIN, NumberDeviceClass, NumberEntity
from homeassistant.const import CONF_DEVICE_CLASS, CONF_UNIT_OF_MEASUREMENT

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_DEFAULT_VALUE, CONF_MAX_VALUE, CONF_MIN_VALUE, CONF_PASSIVE_ENTITY,
    CONF_RESTORE_ON_RECONNECT, CONF_SCALING, CONF_STEPSIZE_VALUE,
)

_LOGGER = logging.getLogger(__name__)
DEFAULT_MIN = 0.0
DEFAULT_MAX = 100000.0
DEFAULT_STEP = 1.0


def _scale_number_value(value, scaling: float) -> float:
    return float(value) * scaling


def _unscale_number_value(value, scaling: float):
    raw_value = round(float(value) / scaling, 10)
    return int(raw_value) if float(raw_value).is_integer() else raw_value


def flow_schema(dps):
    return {
        vol.Optional(CONF_MIN_VALUE, default=DEFAULT_MIN): vol.All(vol.Coerce(float), vol.Range(min=-1000000.0, max=1000000.0)),
        vol.Required(CONF_MAX_VALUE, default=DEFAULT_MAX): vol.All(vol.Coerce(float), vol.Range(min=-1000000.0, max=1000000.0)),
        vol.Required(CONF_STEPSIZE_VALUE, default=DEFAULT_STEP): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1000000.0)),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): str,
        vol.Optional(CONF_SCALING, default=1.0): vol.All(vol.Coerce(float), vol.Range(min=0.000000001, max=1000000000.0)),
        vol.Optional(CONF_DEVICE_CLASS): vol.In([device_class.value for device_class in NumberDeviceClass]),
        vol.Required(CONF_RESTORE_ON_RECONNECT): bool,
        vol.Required(CONF_PASSIVE_ENTITY): bool,
        vol.Optional(CONF_DEFAULT_VALUE): str,
    }


class LocaltuyaNumber(LocalTuyaEntity, NumberEntity):
    def __init__(self, device, config_entry, sensorid, **kwargs):
        super().__init__(device, config_entry, sensorid, _LOGGER, **kwargs)
        self._state = None
        self._scaling = float(self._config.get(CONF_SCALING, 1.0))
        if self._scaling <= 0:
            raise ValueError("Number scaling must be greater than zero")
        self._attr_native_min_value = float(self._config.get(CONF_MIN_VALUE, DEFAULT_MIN))
        self._attr_native_max_value = float(self._config.get(CONF_MAX_VALUE, DEFAULT_MAX))
        self._attr_native_step = float(self._config.get(CONF_STEPSIZE_VALUE, DEFAULT_STEP))
        self._attr_native_unit_of_measurement = self._config.get(CONF_UNIT_OF_MEASUREMENT)
        device_class = self._config.get(CONF_DEVICE_CLASS)
        self._attr_device_class = NumberDeviceClass(device_class) if device_class else None
        default_value = self._config.get(CONF_DEFAULT_VALUE)
        if default_value is not None:
            self._default_value = float(default_value)

    @property
    def native_value(self) -> float | None:
        return self._state

    @property
    def native_min_value(self) -> float:
        metadata = self.mapped_numeric_metadata(self._dp_id)
        value_range = metadata.get("range")
        if isinstance(value_range, dict) and "min" in value_range:
            return float(value_range["min"]) * self._scaling
        return self._attr_native_min_value

    @property
    def native_max_value(self) -> float:
        metadata = self.mapped_numeric_metadata(self._dp_id)
        value_range = metadata.get("range")
        if isinstance(value_range, dict) and "max" in value_range:
            return float(value_range["max"]) * self._scaling
        return self._attr_native_max_value

    @property
    def native_step(self) -> float:
        metadata = self.mapped_numeric_metadata(self._dp_id)
        step = metadata.get("step")
        if isinstance(step, (int, float)) and not isinstance(step, bool) and step > 0:
            return float(step) * self._scaling
        return self._attr_native_step

    def status_updated(self):
        raw_state = self.dps(self._dp_id)
        if raw_state is None or isinstance(raw_state, bool):
            self._state = None
            return
        try:
            value = float(raw_state)
        except (TypeError, ValueError):
            self._state = None
            self.warning("Number entity %s received non-numeric value %r", self.entity_id, raw_state)
            return
        self._state = _scale_number_value(value, self._scaling)
        if not self._device.is_connecting:
            self._last_state = self._state

    async def async_set_native_value(self, value: float) -> None:
        raw_value = _unscale_number_value(value, self._scaling)
        await self.set_mapped_dp(raw_value)

    def entity_default_value(self):
        return self._attr_native_min_value


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaNumber, flow_schema)
