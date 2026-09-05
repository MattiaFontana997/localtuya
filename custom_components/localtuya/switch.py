"""Platform to locally control Tuya-based switch devices."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.switch import DOMAIN, SwitchDeviceClass, SwitchEntity
from homeassistant.const import CONF_DEVICE_CLASS

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    ATTR_CURRENT, ATTR_CURRENT_CONSUMPTION, ATTR_VOLTAGE, CONF_CURRENT,
    CONF_CURRENT_CONSUMPTION, CONF_DEFAULT_VALUE, CONF_PASSIVE_ENTITY,
    CONF_RESTORE_ON_RECONNECT, CONF_VOLTAGE,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    return {
        vol.Optional(CONF_CURRENT): vol.In(dps),
        vol.Optional(CONF_CURRENT_CONSUMPTION): vol.In(dps),
        vol.Optional(CONF_VOLTAGE): vol.In(dps),
        vol.Optional(CONF_DEVICE_CLASS): vol.In([device_class.value for device_class in SwitchDeviceClass]),
        vol.Required(CONF_RESTORE_ON_RECONNECT): bool,
        vol.Required(CONF_PASSIVE_ENTITY): bool,
        vol.Optional(CONF_DEFAULT_VALUE): str,
    }


class LocaltuyaSwitch(LocalTuyaEntity, SwitchEntity):
    def __init__(self, device, config_entry, switchid, **kwargs):
        super().__init__(device, config_entry, switchid, _LOGGER, **kwargs)
        self._state = None
        device_class = self._config.get(CONF_DEVICE_CLASS)
        if device_class:
            try:
                self._attr_device_class = SwitchDeviceClass(device_class)
            except ValueError:
                self.warning("Ignoring unsupported switch device class %r", device_class)

    @property
    def is_on(self) -> bool | None:
        return self._state

    @property
    def extra_state_attributes(self):
        attrs = dict(super().extra_state_attributes)
        if self.has_config(CONF_CURRENT):
            value = self.dps(self._config[CONF_CURRENT])
            if value is not None:
                attrs[ATTR_CURRENT] = value
        if self.has_config(CONF_CURRENT_CONSUMPTION):
            value = self.dps(self._config[CONF_CURRENT_CONSUMPTION])
            attrs[ATTR_CURRENT_CONSUMPTION] = value / 10 if isinstance(value, (int, float)) else value
        if self.has_config(CONF_VOLTAGE):
            value = self.dps(self._config[CONF_VOLTAGE])
            attrs[ATTR_VOLTAGE] = value / 10 if isinstance(value, (int, float)) else value
        return {key: value for key, value in attrs.items() if value is not None}

    def status_updated(self):
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
        await self.set_mapped_dp(True)

    async def async_turn_off(self, **kwargs):
        await self.set_mapped_dp(False)

    def entity_default_value(self):
        return False


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaSwitch, flow_schema)
