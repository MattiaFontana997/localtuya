"""Platform to locally control Tuya lawn mowers."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.lawn_mower import DOMAIN, LawnMowerEntity
from homeassistant.components.lawn_mower.const import (
    SERVICE_DOCK,
    SERVICE_PAUSE,
    SERVICE_START_MOWING,
    LawnMowerActivity,
    LawnMowerEntityFeature,
)

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_LAWN_MOWER_ACTIVITY_DP,
    CONF_LAWN_MOWER_ACTIVITY_VALUES,
    CONF_LAWN_MOWER_COMMAND_DP,
    CONF_LAWN_MOWER_COMMAND_VALUES,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_LAWN_MOWER_ACTIVITY_DP): vol.In(dps),
        vol.Optional(CONF_LAWN_MOWER_COMMAND_DP): vol.In(dps),
    }


def _friendly_for_raw(values, raw):
    if isinstance(values, dict):
        for friendly, configured_raw in values.items():
            if raw == configured_raw:
                return friendly
    return raw if isinstance(raw, str) else None


class LocaltuyaLawnMower(LocalTuyaEntity, LawnMowerEntity):
    """Representation of a Tuya lawn mower."""

    def __init__(self, device, config_entry, mowerid, **kwargs):
        """Initialize the Tuya lawn mower."""
        super().__init__(device, config_entry, mowerid, _LOGGER, **kwargs)
        self._activity_values = self._config.get(CONF_LAWN_MOWER_ACTIVITY_VALUES, {})
        self._command_values = self._config.get(CONF_LAWN_MOWER_COMMAND_VALUES, {})

        features = LawnMowerEntityFeature(0)
        if SERVICE_START_MOWING in self._command_values:
            features |= LawnMowerEntityFeature.START_MOWING
        if SERVICE_PAUSE in self._command_values:
            features |= LawnMowerEntityFeature.PAUSE
        if SERVICE_DOCK in self._command_values:
            features |= LawnMowerEntityFeature.DOCK
        self._attr_supported_features = features

    @property
    def activity(self):
        """Return the current lawn mower activity."""
        dp_id = self._config.get(CONF_LAWN_MOWER_ACTIVITY_DP, self._dp_id)
        friendly = _friendly_for_raw(self._activity_values, self.dps(dp_id))
        if friendly is None:
            return None
        try:
            return LawnMowerActivity(friendly)
        except ValueError:
            self.warning("Ignoring unsupported lawn mower activity %r", friendly)
            return None

    async def _async_command(self, command):
        dp_id = self._config.get(CONF_LAWN_MOWER_COMMAND_DP)
        if dp_id is None or command not in self._command_values:
            raise NotImplementedError()
        await self._device.set_dp(self._command_values[command], dp_id)

    async def async_start_mowing(self):
        """Start mowing."""
        await self._async_command(SERVICE_START_MOWING)

    async def async_pause(self):
        """Pause mowing."""
        await self._async_command(SERVICE_PAUSE)

    async def async_dock(self):
        """Return the mower to its dock."""
        await self._async_command(SERVICE_DOCK)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaLawnMower, flow_schema)
