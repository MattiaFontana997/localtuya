"""Platform to present any Tuya DP as a sensor."""

import logging
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
from .const import CONF_SCALING

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

    def status_updated(self):
        """Update the native sensor value."""
        state = self.dps(self._dp_id)

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
