"""Platform to present any Tuya DP as a binary sensor."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_DEVICE_CLASS

from .common import LocalTuyaEntity, async_setup_entry
from .const import CONF_STATE_OFF, CONF_STATE_ON

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Required(CONF_STATE_ON, default="True"): str,
        vol.Required(CONF_STATE_OFF, default="False"): str,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }


class LocaltuyaBinarySensor(LocalTuyaEntity, BinarySensorEntity):
    """Representation of a Tuya binary sensor."""

    def __init__(
        self,
        device,
        config_entry,
        sensorid,
        **kwargs,
    ):
        """Initialize the Tuya binary sensor."""
        super().__init__(device, config_entry, sensorid, _LOGGER, **kwargs)

        self._attr_is_on = None

        device_class = self._config.get(CONF_DEVICE_CLASS)
        self._attr_device_class = (
            BinarySensorDeviceClass(device_class)
            if device_class
            else None
        )

    def status_updated(self):
        """Update binary sensor state."""
        raw_state = self.dps(self._dp_id)

        if raw_state is None:
            self._attr_is_on = None
            return

        state = str(raw_state).lower()

        if state == self._config[CONF_STATE_ON].lower():
            self._attr_is_on = True
        elif state == self._config[CONF_STATE_OFF].lower():
            self._attr_is_on = False
        else:
            self._attr_is_on = None
            self.warning(
                "State for entity %s did not match configured state patterns",
                self.entity_id,
            )

    async def restore_state_when_connected(self):
        """Binary sensors do not restore values to the Tuya device."""
        return


async_setup_entry = partial(
    async_setup_entry,
    DOMAIN,
    LocaltuyaBinarySensor,
    flow_schema,
)
