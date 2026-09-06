"""Platform to expose Tuya string datapoints as Home Assistant text entities."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.text import DOMAIN, TextEntity, TextMode

from .common import LocalTuyaEntity, async_setup_entry
from .const import CONF_TEXT_MAX, CONF_TEXT_MIN, CONF_TEXT_MODE, CONF_TEXT_PATTERN

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_TEXT_MIN, default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
        vol.Optional(CONF_TEXT_MAX, default=255): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Optional(CONF_TEXT_PATTERN): str,
        vol.Optional(CONF_TEXT_MODE, default=TextMode.TEXT.value): vol.In(
            [mode.value for mode in TextMode]
        ),
    }


class LocaltuyaText(LocalTuyaEntity, TextEntity):
    """Representation of a Tuya text datapoint."""

    def __init__(self, device, config_entry, textid, **kwargs):
        """Initialize the Tuya text entity."""
        super().__init__(device, config_entry, textid, _LOGGER, **kwargs)
        self._state = None

        minimum = int(self._config.get(CONF_TEXT_MIN, 0))
        maximum = int(self._config.get(CONF_TEXT_MAX, 255))
        if minimum < 0 or maximum < minimum:
            raise ValueError("Invalid text length range")
        self._attr_native_min = minimum
        self._attr_native_max = maximum

        pattern = self._config.get(CONF_TEXT_PATTERN)
        if isinstance(pattern, str) and pattern:
            self._attr_pattern = pattern

        mode = self._config.get(CONF_TEXT_MODE, TextMode.TEXT.value)
        try:
            self._attr_mode = TextMode(mode)
        except ValueError:
            self._attr_mode = TextMode.TEXT

    @property
    def native_value(self) -> str | None:
        """Return the current text value."""
        return self._state

    def status_updated(self):
        """Update text state from the Tuya DP."""
        raw_state = self.dps(self._dp_id)
        self._state = raw_state if isinstance(raw_state, str) else None

    async def async_set_value(self, value: str) -> None:
        """Set the raw Tuya text value."""
        await self._device.set_dp(value, self._dp_id)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaText, flow_schema)
