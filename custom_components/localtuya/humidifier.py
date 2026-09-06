"""Platform to locally control Tuya-based humidifier devices."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.humidifier import (
    DOMAIN,
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.components.humidifier.const import DEFAULT_MAX_HUMIDITY, DEFAULT_MIN_HUMIDITY
from homeassistant.const import CONF_DEVICE_CLASS

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_HUMIDIFIER_ACTION_DP,
    CONF_HUMIDIFIER_ACTION_VALUES,
    CONF_HUMIDIFIER_CURRENT_HUMIDITY_DP,
    CONF_HUMIDIFIER_HUMIDITY_MAX,
    CONF_HUMIDIFIER_HUMIDITY_MIN,
    CONF_HUMIDIFIER_HUMIDITY_SCALING,
    CONF_HUMIDIFIER_HUMIDITY_STEP,
    CONF_HUMIDIFIER_MODE_DP,
    CONF_HUMIDIFIER_MODE_VALUES,
    CONF_HUMIDIFIER_SWITCH_DP,
    CONF_HUMIDIFIER_SWITCH_OFF,
    CONF_HUMIDIFIER_SWITCH_ON,
    CONF_HUMIDIFIER_TARGET_HUMIDITY_DP,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_HUMIDIFIER_SWITCH_DP): vol.In(dps),
        vol.Optional(CONF_HUMIDIFIER_CURRENT_HUMIDITY_DP): vol.In(dps),
        vol.Optional(CONF_HUMIDIFIER_TARGET_HUMIDITY_DP): vol.In(dps),
        vol.Optional(CONF_HUMIDIFIER_MODE_DP): vol.In(dps),
        vol.Optional(CONF_HUMIDIFIER_ACTION_DP): vol.In(dps),
        vol.Optional(CONF_DEVICE_CLASS): vol.In(
            [device_class.value for device_class in HumidifierDeviceClass]
        ),
    }


def _decode(values, raw):
    if isinstance(values, dict):
        for friendly, configured_raw in values.items():
            if raw == configured_raw:
                return friendly
    return raw


def _scaled(value, scaling):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) * scaling


def _unscaled(value, scaling):
    raw = float(value) / scaling
    raw = round(raw, 10)
    return int(raw) if float(raw).is_integer() else raw


class LocaltuyaHumidifier(LocalTuyaEntity, HumidifierEntity):
    """Representation of a Tuya humidifier or dehumidifier."""

    def __init__(self, device, config_entry, humidifierid, **kwargs):
        """Initialize the Tuya humidifier."""
        super().__init__(device, config_entry, humidifierid, _LOGGER, **kwargs)

        self._scaling = float(self._config.get(CONF_HUMIDIFIER_HUMIDITY_SCALING, 1.0))
        if self._scaling <= 0:
            raise ValueError("Humidifier scaling must be greater than zero")

        self._attr_min_humidity = float(
            self._config.get(CONF_HUMIDIFIER_HUMIDITY_MIN, DEFAULT_MIN_HUMIDITY)
        )
        self._attr_max_humidity = float(
            self._config.get(CONF_HUMIDIFIER_HUMIDITY_MAX, DEFAULT_MAX_HUMIDITY)
        )
        self._attr_target_humidity_step = float(
            self._config.get(CONF_HUMIDIFIER_HUMIDITY_STEP, 1.0)
        )

        self._switch_on = self._config.get(CONF_HUMIDIFIER_SWITCH_ON, True)
        self._switch_off = self._config.get(CONF_HUMIDIFIER_SWITCH_OFF, False)
        self._mode_values = self._config.get(CONF_HUMIDIFIER_MODE_VALUES, {})
        self._action_values = self._config.get(CONF_HUMIDIFIER_ACTION_VALUES, {})

        self._attr_supported_features = HumidifierEntityFeature(0)
        if self.has_config(CONF_HUMIDIFIER_MODE_DP) and self._mode_values:
            self._attr_supported_features |= HumidifierEntityFeature.MODES

        device_class = self._config.get(CONF_DEVICE_CLASS)
        if device_class:
            try:
                self._attr_device_class = HumidifierDeviceClass(device_class)
            except ValueError:
                self.warning("Ignoring unsupported humidifier device class %r", device_class)

    @property
    def is_on(self) -> bool | None:
        """Return whether the humidifier is on."""
        if not self.has_config(CONF_HUMIDIFIER_SWITCH_DP):
            return self.available
        raw = self.dps(self._config[CONF_HUMIDIFIER_SWITCH_DP])
        if raw == self._switch_on:
            return True
        if raw == self._switch_off:
            return False
        return None

    @property
    def current_humidity(self) -> float | None:
        """Return current humidity."""
        if not self.has_config(CONF_HUMIDIFIER_CURRENT_HUMIDITY_DP):
            return None
        return _scaled(
            self.dps(self._config[CONF_HUMIDIFIER_CURRENT_HUMIDITY_DP]),
            self._scaling,
        )

    @property
    def target_humidity(self) -> float | None:
        """Return target humidity."""
        dp_id = self._config.get(CONF_HUMIDIFIER_TARGET_HUMIDITY_DP)
        if dp_id is None:
            return None
        return _scaled(self.dps(dp_id), self._scaling)

    @property
    def mode(self) -> str | None:
        """Return current mode."""
        if not self.has_config(CONF_HUMIDIFIER_MODE_DP):
            return None
        return _decode(
            self._mode_values,
            self.dps(self._config[CONF_HUMIDIFIER_MODE_DP]),
        )

    @property
    def available_modes(self) -> list[str] | None:
        """Return available modes."""
        return list(self._mode_values) if self._mode_values else None

    @property
    def action(self):
        """Return current humidifier action."""
        if self.is_on is False:
            return HumidifierAction.OFF
        if not self.has_config(CONF_HUMIDIFIER_ACTION_DP):
            return None
        value = _decode(
            self._action_values,
            self.dps(self._config[CONF_HUMIDIFIER_ACTION_DP]),
        )
        if not value:
            return None
        try:
            return HumidifierAction(value)
        except ValueError:
            self.warning("Ignoring unsupported humidifier action %r", value)
            return None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the humidifier on."""
        if not self.has_config(CONF_HUMIDIFIER_SWITCH_DP):
            raise NotImplementedError()
        await self._device.set_dp(
            self._switch_on,
            self._config[CONF_HUMIDIFIER_SWITCH_DP],
        )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the humidifier off."""
        if not self.has_config(CONF_HUMIDIFIER_SWITCH_DP):
            raise NotImplementedError()
        await self._device.set_dp(
            self._switch_off,
            self._config[CONF_HUMIDIFIER_SWITCH_DP],
        )

    async def async_set_humidity(self, humidity: int) -> None:
        """Set target humidity."""
        dp_id = self._config.get(CONF_HUMIDIFIER_TARGET_HUMIDITY_DP)
        if dp_id is None:
            raise NotImplementedError()
        await self._device.set_dp(_unscaled(humidity, self._scaling), dp_id)

    async def async_set_mode(self, mode: str) -> None:
        """Set the exact catalog-provided raw humidifier mode."""
        dp_id = self._config.get(CONF_HUMIDIFIER_MODE_DP)
        if dp_id is None or mode not in self._mode_values:
            raise NotImplementedError()
        await self._device.set_dp(self._mode_values[mode], dp_id)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaHumidifier, flow_schema)
