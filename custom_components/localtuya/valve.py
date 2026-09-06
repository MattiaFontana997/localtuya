"""Platform to locally control Tuya-based valve devices."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.valve import DOMAIN, ValveDeviceClass, ValveEntity, ValveEntityFeature
from homeassistant.const import CONF_DEVICE_CLASS

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_VALVE_CLOSED_VALUE,
    CONF_VALVE_CURRENT_POSITION_DP,
    CONF_VALVE_OPEN_VALUE,
    CONF_VALVE_POSITION_CONTROL,
    CONF_VALVE_POSITION_INVERTED,
    CONF_VALVE_POSITION_MAX,
    CONF_VALVE_POSITION_MIN,
    CONF_VALVE_SWITCH_DP,
    CONF_VALVE_SWITCH_OFF,
    CONF_VALVE_SWITCH_ON,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_VALVE_SWITCH_DP): vol.In(dps),
        vol.Optional(CONF_VALVE_CURRENT_POSITION_DP): vol.In(dps),
        vol.Optional(CONF_DEVICE_CLASS): vol.In(
            [device_class.value for device_class in ValveDeviceClass]
        ),
    }


def _position_from_raw(value, minimum, maximum, inverted):
    """Convert a raw valve range to Home Assistant percent."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if maximum <= minimum:
        return None
    position = (float(value) - minimum) * 100.0 / (maximum - minimum)
    if inverted:
        position = 100.0 - position
    return max(0, min(100, round(position)))


def _position_to_raw(position, minimum, maximum, inverted):
    """Convert Home Assistant percent to the configured raw valve range."""
    percent = max(0.0, min(100.0, float(position)))
    if inverted:
        percent = 100.0 - percent
    raw = minimum + (maximum - minimum) * percent / 100.0
    return int(round(raw)) if float(raw).is_integer() else raw


class LocaltuyaValve(LocalTuyaEntity, ValveEntity):
    """Representation of a Tuya valve."""

    def __init__(self, device, config_entry, valveid, **kwargs):
        """Initialize the Tuya valve."""
        super().__init__(device, config_entry, valveid, _LOGGER, **kwargs)

        self._position_control = bool(self._config.get(CONF_VALVE_POSITION_CONTROL, False))
        self._position_min = float(self._config.get(CONF_VALVE_POSITION_MIN, 0))
        self._position_max = float(self._config.get(CONF_VALVE_POSITION_MAX, 100))
        self._position_inverted = bool(self._config.get(CONF_VALVE_POSITION_INVERTED, False))
        self._open_value = self._config.get(CONF_VALVE_OPEN_VALUE, True)
        self._closed_value = self._config.get(CONF_VALVE_CLOSED_VALUE, False)
        self._switch_on = self._config.get(CONF_VALVE_SWITCH_ON, True)
        self._switch_off = self._config.get(CONF_VALVE_SWITCH_OFF, False)

        self._attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
        if self._position_control:
            self._attr_supported_features |= ValveEntityFeature.SET_POSITION

        device_class = self._config.get(CONF_DEVICE_CLASS)
        if device_class:
            try:
                self._attr_device_class = ValveDeviceClass(device_class)
            except ValueError:
                self.warning("Ignoring unsupported valve device class %r", device_class)

    @property
    def current_valve_position(self) -> int | None:
        """Return the valve position as a percentage when available."""
        if not self._position_control:
            return None
        dp_id = self._config.get(CONF_VALVE_CURRENT_POSITION_DP, self._dp_id)
        return _position_from_raw(
            self.dps(dp_id),
            self._position_min,
            self._position_max,
            self._position_inverted,
        )

    @property
    def is_closed(self) -> bool | None:
        """Return whether the valve is closed."""
        switch_dp = self._config.get(CONF_VALVE_SWITCH_DP)
        if switch_dp is not None:
            raw_switch = self.dps(switch_dp)
            if raw_switch == self._switch_off:
                return True
            if raw_switch == self._switch_on:
                return False

        if self._position_control:
            position = self.current_valve_position
            return None if position is None else position == 0

        raw_state = self.dps(self._dp_id)
        if raw_state == self._closed_value:
            return True
        if raw_state == self._open_value:
            return False
        return None

    async def async_open_valve(self) -> None:
        """Open the valve."""
        switch_dp = self._config.get(CONF_VALVE_SWITCH_DP)
        if switch_dp is not None:
            await self._device.set_dp(self._switch_on, switch_dp)

        if self._position_control:
            raw = _position_to_raw(
                100,
                self._position_min,
                self._position_max,
                self._position_inverted,
            )
            await self._device.set_dp(raw, self._dp_id)
        elif switch_dp is None or self._dp_id != switch_dp:
            await self._device.set_dp(self._open_value, self._dp_id)

    async def async_close_valve(self) -> None:
        """Close the valve."""
        switch_dp = self._config.get(CONF_VALVE_SWITCH_DP)
        if switch_dp is not None:
            await self._device.set_dp(self._switch_off, switch_dp)
        else:
            raw = (
                _position_to_raw(
                    0,
                    self._position_min,
                    self._position_max,
                    self._position_inverted,
                )
                if self._position_control
                else self._closed_value
            )
            await self._device.set_dp(raw, self._dp_id)

    async def async_set_valve_position(self, position: int) -> None:
        """Set the valve position."""
        if not self._position_control:
            raise NotImplementedError()
        raw = _position_to_raw(
            position,
            self._position_min,
            self._position_max,
            self._position_inverted,
        )
        switch_dp = self._config.get(CONF_VALVE_SWITCH_DP)
        if switch_dp is not None and position > 0:
            await self._device.set_dp(self._switch_on, switch_dp)
        await self._device.set_dp(raw, self._dp_id)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaValve, flow_schema)
