"""Platform to expose Tuya datapoints as Home Assistant buttons."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.button import ButtonDeviceClass, ButtonEntity, DOMAIN
from homeassistant.const import CONF_DEVICE_CLASS

from .common import LocalTuyaEntity, async_setup_entry
from .const import CONF_BUTTON_PRESS_VALUE

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_DEVICE_CLASS): vol.In(
            [device_class.value for device_class in ButtonDeviceClass]
        ),
    }


class LocaltuyaButton(LocalTuyaEntity, ButtonEntity):
    """Representation of a Tuya button."""

    def __init__(self, device, config_entry, buttonid, **kwargs):
        """Initialize the Tuya button."""
        super().__init__(device, config_entry, buttonid, _LOGGER, **kwargs)
        self._press_value = self._config.get(CONF_BUTTON_PRESS_VALUE, True)

        device_class = self._config.get(CONF_DEVICE_CLASS)
        if device_class:
            try:
                self._attr_device_class = ButtonDeviceClass(device_class)
            except ValueError:
                self.warning("Ignoring unsupported button device class %r", device_class)

    async def async_press(self) -> None:
        """Press the Tuya button using its configured raw trigger value."""
        await self._device.set_dp(self._press_value, self._dp_id)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaButton, flow_schema)
