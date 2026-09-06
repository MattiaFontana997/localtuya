"""Platform to present any Tuya DP as a sensor."""

import logging
from datetime import UTC, datetime
from functools import partial

import voluptuous as vol
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)

from .common import LocalTuyaEntity, async_setup_entry
from .const import CONF_SCALING, CONF_SENSOR_UNIX_TIMESTAMP
from .sensor_mapping import evaluate_sensor_value_mapping, validate_sensor_value_mapping

_LOGGER = logging.getLogger(__name__)

DEFAULT_PRECISION = 2


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): str,
        vol.Optional(CONF_DEVICE_CLASS): vol.In(
            [device_class.value for device_class in SensorDeviceClass]
        ),
        vol.Optional(CONF_STATE_CLASS): vol.In(
            [state_class.value for state_class in SensorStateClass]
        ),
        vol.Optional(CONF_SCALING): vol.All(
            vol.Coerce(float),
            vol.Range(min=-1000000.0, max=1000000.0),
        ),
        vol.Optional(CONF_SENSOR_UNIX_TIMESTAMP, default=False): bool,
    }


class LocaltuyaSensor(LocalTuyaEntity, SensorEntity):
    """Representation of a Tuya sensor."""

    def __init__(
        self,
        device,
        config_entry,
        sensorid,
        **kwargs,
    ):
        """Initialize the Tuya sensor."""
        super().__init__(device, config_entry, sensorid, _LOGGER, **kwargs)

        self._state = None
        self._value_mapping = validate_sensor_value_mapping(self._config.get("sensor_value_mapping"))
        self._mapping_icon = None

        device_class = self._config.get(CONF_DEVICE_CLASS)
        self._attr_device_class = (
            SensorDeviceClass(device_class)
            if device_class
            else None
        )

        state_class = self._config.get(CONF_STATE_CLASS)
        self._attr_state_class = (
            SensorStateClass(state_class)
            if state_class
            else None
        )

        self._attr_native_unit_of_measurement = self._config.get(
            CONF_UNIT_OF_MEASUREMENT
        )

    @property
    def native_value(self):
        """Return the native sensor value."""
        return self._state

    @property
    def options(self):
        if self._value_mapping is None:
            return None
        values = [rule["value"] for rule in self._value_mapping["rules"] if "value" in rule]
        return list(dict.fromkeys(values)) if any(isinstance(v, str) for v in values) else None

    @property
    def icon(self):
        return self._mapping_icon or super().icon

    def status_updated(self):
        """Update the native sensor value."""
        state = self.dps(self._dp_id)
        if self._value_mapping is not None:
            self._state, self._mapping_icon = evaluate_sensor_value_mapping(state, self._value_mapping)
            return

        if self._config.get(CONF_SENSOR_UNIX_TIMESTAMP):
            if isinstance(state, bool) or not isinstance(state, (int, float)):
                self._state = None
                return
            try:
                self._state = datetime.fromtimestamp(state, UTC)
            except (OverflowError, OSError, ValueError):
                self._state = None
            return

        scale_factor = self._config.get(CONF_SCALING)
        if (
            scale_factor is not None
            and isinstance(state, (int, float))
            and not isinstance(state, bool)
        ):
            state = round(
                state * scale_factor,
                DEFAULT_PRECISION,
            )

        self._state = state

    async def restore_state_when_connected(self):
        """Sensors do not restore values to the Tuya device."""
        return


async_setup_entry = partial(
    async_setup_entry,
    DOMAIN,
    LocaltuyaSensor,
    flow_schema,
)
