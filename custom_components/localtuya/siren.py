"""Platform to locally control Tuya sirens."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.siren import DOMAIN, SirenEntity, SirenEntityFeature
from homeassistant.components.siren.const import ATTR_DURATION, ATTR_TONE, ATTR_VOLUME_LEVEL

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_SIREN_DEFAULT_TONE,
    CONF_SIREN_DURATION_DP,
    CONF_SIREN_DURATION_SCALING,
    CONF_SIREN_SWITCH_DP,
    CONF_SIREN_SWITCH_OFF,
    CONF_SIREN_SWITCH_ON,
    CONF_SIREN_TONE_DP,
    CONF_SIREN_TONE_VALUES,
    CONF_SIREN_VOLUME_DP,
    CONF_SIREN_VOLUME_SCALING,
    CONF_SIREN_VOLUME_VALUES,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    return {
        vol.Optional(CONF_SIREN_SWITCH_DP): vol.In(dps),
        vol.Optional(CONF_SIREN_TONE_DP): vol.In(dps),
        vol.Optional(CONF_SIREN_DURATION_DP): vol.In(dps),
        vol.Optional(CONF_SIREN_VOLUME_DP): vol.In(dps),
    }


def _decode(values, raw):
    for friendly, configured_raw in (values or {}).items():
        if raw == configured_raw:
            return friendly
    return raw


class LocaltuyaSiren(LocalTuyaEntity, SirenEntity):
    def __init__(self, device, config_entry, dp_id, **kwargs):
        super().__init__(device, config_entry, dp_id, _LOGGER, **kwargs)
        self._tone_values = self._config.get(CONF_SIREN_TONE_VALUES, {})
        self._volume_values = self._config.get(CONF_SIREN_VOLUME_VALUES, {})
        support = SirenEntityFeature(0)
        if self.has_config(CONF_SIREN_TONE_DP):
            support |= SirenEntityFeature.TONES | SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
            self._attr_available_tones = [tone for tone in self._tone_values if tone != "off"]
        if self.has_config(CONF_SIREN_VOLUME_DP):
            support |= SirenEntityFeature.VOLUME_SET
        if self.has_config(CONF_SIREN_DURATION_DP):
            support |= SirenEntityFeature.DURATION
        if self.has_config(CONF_SIREN_SWITCH_DP):
            support |= SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
        self._attr_supported_features = support

    @property
    def is_on(self):
        if self.has_config(CONF_SIREN_SWITCH_DP):
            raw = self.dps(self._config[CONF_SIREN_SWITCH_DP])
            if raw == self._config.get(CONF_SIREN_SWITCH_ON, True):
                return True
            if raw == self._config.get(CONF_SIREN_SWITCH_OFF, False):
                return False
            return None
        if self.has_config(CONF_SIREN_TONE_DP):
            return _decode(self._tone_values, self.dps(self._config[CONF_SIREN_TONE_DP])) != "off"
        return None

    def _volume_raw(self, volume):
        if self._volume_values:
            choices = [(float(level), raw) for level, raw in self._volume_values.items()]
            return min(choices, key=lambda item: abs(item[0] - float(volume)))[1]
        factor = float(self._config.get(CONF_SIREN_VOLUME_SCALING, 1.0))
        raw = float(volume) / factor
        raw = round(raw, 10)
        return int(raw) if float(raw).is_integer() else raw

    async def async_turn_on(self, **kwargs):
        settings = {}
        tone = kwargs.get(ATTR_TONE)
        if self.has_config(CONF_SIREN_TONE_DP):
            if tone is None and not self.has_config(CONF_SIREN_SWITCH_DP):
                current = _decode(self._tone_values, self.dps(self._config[CONF_SIREN_TONE_DP]))
                if current == "off" or current not in self._tone_values:
                    tone = self._config.get(CONF_SIREN_DEFAULT_TONE)
            if tone is not None:
                if tone not in self._tone_values:
                    raise ValueError(f"Unsupported siren tone {tone!r}")
                settings[self._config[CONF_SIREN_TONE_DP]] = self._tone_values[tone]
        if kwargs.get(ATTR_DURATION) is not None and self.has_config(CONF_SIREN_DURATION_DP):
            factor = float(self._config.get(CONF_SIREN_DURATION_SCALING, 1.0))
            raw = float(kwargs[ATTR_DURATION]) / factor
            settings[self._config[CONF_SIREN_DURATION_DP]] = int(raw) if raw.is_integer() else raw
        if kwargs.get(ATTR_VOLUME_LEVEL) is not None and self.has_config(CONF_SIREN_VOLUME_DP):
            settings[self._config[CONF_SIREN_VOLUME_DP]] = self._volume_raw(kwargs[ATTR_VOLUME_LEVEL])
        if self.has_config(CONF_SIREN_SWITCH_DP) and self.is_on is not True:
            settings[self._config[CONF_SIREN_SWITCH_DP]] = self._config.get(CONF_SIREN_SWITCH_ON, True)
        if not settings:
            raise NotImplementedError()
        await self._device.set_dps(settings)

    async def async_turn_off(self):
        if self.has_config(CONF_SIREN_SWITCH_DP):
            await self._device.set_dp(self._config.get(CONF_SIREN_SWITCH_OFF, False), self._config[CONF_SIREN_SWITCH_DP])
            return
        if self.has_config(CONF_SIREN_TONE_DP) and "off" in self._tone_values:
            await self._device.set_dp(self._tone_values["off"], self._config[CONF_SIREN_TONE_DP])
            return
        raise NotImplementedError()


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaSiren, flow_schema)
