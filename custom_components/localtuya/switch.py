"""Platform to locally control Tuya-based switch devices."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.switch import DOMAIN, SwitchEntity

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    ATTR_CURRENT,
    ATTR_CURRENT_CONSUMPTION,
    ATTR_VOLTAGE,
    CONF_CURRENT,
    CONF_CURRENT_CONSUMPTION,
    CONF_DEFAULT_VALUE,
    CONF_PASSIVE_ENTITY,
    CONF_RESTORE_ON_RECONNECT,
    CONF_VOLTAGE,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_CURRENT): vol.In(dps),
        vol.Optional(CONF_CURRENT_CONSUMPTION): vol.In(dps),
        vol.Optional(CONF_VOLTAGE): vol.In(dps),
        vol.Required(CONF_RESTORE_ON_RECONNECT): bool,
        vol.Required(CONF_PASSIVE_ENTITY): bool,
        vol.Optional(CONF_DEFAULT_VALUE): str,
    }


class LocaltuyaSwitch(LocalTuyaEntity, SwitchEntity):
    """Representation of a Tuya switch."""

    def __init__(
        self,
        device,
        config_entry,
        switchid,
        **kwargs,
    ):
        """Initialize the Tuya switch."""
        super().__init__(device, config_entry, switchid, _LOGGER, **kwargs)
        self._state = None

    @property
    def is_on(self) -> bool | None:
        """Return whether the Tuya switch is on."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return legacy electrical measurements and restore state."""
        attrs = dict(super().extra_state_attributes)

        if self.has_config(CONF_CURRENT):
            value = self.dps(self._config[CONF_CURRENT])
            if value is not None:
                attrs[ATTR_CURRENT] = value

        if self.has_config(CONF_CURRENT_CONSUMPTION):
            value = self.dps(self._config[CONF_CURRENT_CONSUMPTION])
            if isinstance(value, (int, float)):
                attrs[ATTR_CURRENT_CONSUMPTION] = value / 10
            elif value is not None:
                attrs[ATTR_CURRENT_CONSUMPTION] = value

        if self.has_config(CONF_VOLTAGE):
            value = self.dps(self._config[CONF_VOLTAGE])
            if isinstance(value, (int, float)):
                attrs[ATTR_VOLTAGE] = value / 10
            elif value is not None:
                attrs[ATTR_VOLTAGE] = value

        return attrs

    def status_updated(self):
        """Update switch state."""
        raw_state = self.dps(self._dp_id)

        if isinstance(raw_state, bool):
            state = raw_state
        elif raw_state in (0, 1):
            state = bool(raw_state)
        else:
            state = None

        self._state = state

        if state is not None and not self._device.is_connecting:
            self._last_state = state

    async def async_turn_on(self, **kwargs):
        """Turn the Tuya switch on."""
        await self._device.set_dp(True, self._dp_id)

    async def async_turn_off(self, **kwargs):
        """Turn the Tuya switch off."""
        await self._device.set_dp(False, self._dp_id)

    def entity_default_value(self):
        """Return False as the default switch value."""
        return False


async_setup_entry = partial(
    async_setup_entry,
    DOMAIN,
    LocaltuyaSwitch,
    flow_schema,
)
