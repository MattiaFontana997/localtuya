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
    CONF_RESTORE_ON_RECONNECT, CONF_SWITCH_ICON_OFF, CONF_SWITCH_ICON_ON,
    CONF_SWITCH_MASK, CONF_SWITCH_MASK_ENDIANNESS, CONF_SWITCH_OFF_VALUE,
    CONF_SWITCH_ON_VALUE, CONF_VOLTAGE,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    return {
        vol.Optional(CONF_CURRENT): vol.In(dps),
        vol.Optional(CONF_CURRENT_CONSUMPTION): vol.In(dps),
        vol.Optional(CONF_VOLTAGE): vol.In(dps),
        vol.Optional(CONF_DEVICE_CLASS): vol.In([device_class.value for device_class in SwitchDeviceClass]),
        vol.Optional(CONF_SWITCH_ON_VALUE): vol.Any(str, int, bool),
        vol.Optional(CONF_SWITCH_OFF_VALUE): vol.Any(str, int, bool),
        vol.Optional(CONF_SWITCH_ICON_ON): str,
        vol.Optional(CONF_SWITCH_ICON_OFF): str,
        vol.Optional(CONF_SWITCH_MASK): str,
        vol.Optional(CONF_SWITCH_MASK_ENDIANNESS, default="big"): vol.In(("big", "little")),
        vol.Required(CONF_RESTORE_ON_RECONNECT): bool,
        vol.Required(CONF_PASSIVE_ENTITY): bool,
        vol.Optional(CONF_DEFAULT_VALUE): str,
    }


class LocaltuyaSwitch(LocalTuyaEntity, SwitchEntity):
    def __init__(self, device, config_entry, switchid, **kwargs):
        super().__init__(device, config_entry, switchid, _LOGGER, **kwargs)
        self._state = None
        self._mapping_icon = None
        self._switch_on_value = self._config.get(CONF_SWITCH_ON_VALUE)
        self._switch_off_value = self._config.get(CONF_SWITCH_OFF_VALUE)
        mask_text = self._config.get(CONF_SWITCH_MASK)
        self._switch_mask_text = mask_text if isinstance(mask_text, str) else None
        self._switch_mask = int(mask_text, 16) if self._switch_mask_text else None
        self._switch_mask_endianness = self._config.get(CONF_SWITCH_MASK_ENDIANNESS, "big")
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
    def icon(self):
        return self._mapping_icon or super().icon

    def _masked_state(self, raw_state):
        if self._switch_mask is None or not isinstance(raw_state, str):
            return None
        try:
            value_text = raw_state if len(raw_state) % 2 == 0 else "0" + raw_state
            raw_bytes = bytes.fromhex(value_text)
            value = int.from_bytes(raw_bytes, self._switch_mask_endianness)
        except (ValueError, TypeError):
            return None
        scale = self._switch_mask & (1 + ~self._switch_mask)
        return bool((value & self._switch_mask) // scale)

    def _masked_write_value(self, enabled):
        raw_state = self.dps(self._dp_id)
        if not isinstance(raw_state, str) or self._switch_mask is None or not self._switch_mask_text:
            raise ValueError("Cannot mask unknown current switch value")
        try:
            value_text = raw_state if len(raw_state) % 2 == 0 else "0" + raw_state
            raw_bytes = bytes.fromhex(value_text)
            length = len(self._switch_mask_text) // 2
            current = int.from_bytes(raw_bytes, self._switch_mask_endianness)
            scale = self._switch_mask & (1 + ~self._switch_mask)
            result = (current & ~self._switch_mask) | (
                self._switch_mask & int(bool(enabled) * scale)
            )
            return result.to_bytes(length, self._switch_mask_endianness).hex()
        except (ValueError, OverflowError) as err:
            raise ValueError("Cannot mask invalid current switch value") from err

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
        if self._switch_mask is not None:
            state = self._masked_state(raw_state)
        elif CONF_SWITCH_ON_VALUE in self._config and CONF_SWITCH_OFF_VALUE in self._config:
            if raw_state == self._switch_on_value:
                state = True
            elif raw_state == self._switch_off_value:
                state = False
            else:
                state = None
        elif isinstance(raw_state, bool):
            state = raw_state
        elif raw_state in (0, 1):
            state = bool(raw_state)
        else:
            state = None
        self._state = state
        if state is True:
            self._mapping_icon = self._config.get(CONF_SWITCH_ICON_ON)
        elif state is False:
            self._mapping_icon = self._config.get(CONF_SWITCH_ICON_OFF)
        else:
            self._mapping_icon = None
        if state is not None and not self._device.is_connecting:
            self._last_state = state

    async def async_turn_on(self, **kwargs):
        if self._switch_mask is not None:
            await self._device.set_dp(self._masked_write_value(True), self._dp_id)
        elif CONF_SWITCH_ON_VALUE in self._config:
            await self._device.set_dp(self._switch_on_value, self._dp_id)
        else:
            await self.set_mapped_dp(True)

    async def async_turn_off(self, **kwargs):
        if self._switch_mask is not None:
            await self._device.set_dp(self._masked_write_value(False), self._dp_id)
        elif CONF_SWITCH_OFF_VALUE in self._config:
            await self._device.set_dp(self._switch_off_value, self._dp_id)
        else:
            await self.set_mapped_dp(False)

    def entity_default_value(self):
        return False


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaSwitch, flow_schema)
