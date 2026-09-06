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
    CONF_SIREN_VOLUME_MAX,
    CONF_SIREN_VOLUME_MIN,
    CONF_SIREN_VOLUME_VALUES,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_SIREN_SWITCH_DP): vol.In(dps),
        vol.Optional(CONF_SIREN_TONE_DP): vol.In(dps),
        vol.Optional(CONF_SIREN_DURATION_DP): vol.In(dps),
        vol.Optional(CONF_SIREN_VOLUME_DP): vol.In(dps),
    }


def _friendly_for_raw(values, raw):
    if not isinstance(values, dict):
        return None
    for friendly, configured_raw in values.items():
        if raw == configured_raw:
            return friendly
    return None


def _duration_to_raw(duration, scaling):
    raw = round(float(duration) / scaling, 10)
    return int(raw) if float(raw).is_integer() else raw


def _volume_levels(values):
    """Return normalized HA volume levels mapped to exact raw values."""
    result = {}
    if not isinstance(values, dict):
        return result
    for key, raw in values.items():
        try:
            level = float(key)
        except (TypeError, ValueError):
            continue
        if 0.0 <= level <= 1.0:
            result[level] = raw
    return result


class LocaltuyaSiren(LocalTuyaEntity, SirenEntity):
    """Representation of a Tuya siren."""

    def __init__(self, device, config_entry, sirenid, **kwargs):
        """Initialize the Tuya siren."""
        super().__init__(device, config_entry, sirenid, _LOGGER, **kwargs)
        self._switch_on = self._config.get(CONF_SIREN_SWITCH_ON, True)
        self._switch_off = self._config.get(CONF_SIREN_SWITCH_OFF, False)
        self._tone_values = self._config.get(CONF_SIREN_TONE_VALUES, {})
        self._default_tone = self._config.get(CONF_SIREN_DEFAULT_TONE)
        self._duration_scaling = float(self._config.get(CONF_SIREN_DURATION_SCALING, 1.0))
        if self._duration_scaling <= 0:
            raise ValueError("Siren duration scaling must be greater than zero")
        self._volume_min = float(self._config.get(CONF_SIREN_VOLUME_MIN, 0.0))
        self._volume_max = float(self._config.get(CONF_SIREN_VOLUME_MAX, 100.0))
        if self._volume_max <= self._volume_min:
            raise ValueError("Invalid siren volume range")
        self._volume_values = _volume_levels(self._config.get(CONF_SIREN_VOLUME_VALUES, {}))

        features = SirenEntityFeature(0)
        if self.has_config(CONF_SIREN_SWITCH_DP) or self.has_config(CONF_SIREN_TONE_DP):
            features |= SirenEntityFeature.TURN_ON
        if self.has_config(CONF_SIREN_SWITCH_DP) or "off" in self._tone_values:
            features |= SirenEntityFeature.TURN_OFF
        tones = [tone for tone in self._tone_values if tone != "off"]
        if self.has_config(CONF_SIREN_TONE_DP) and tones:
            features |= SirenEntityFeature.TONES
            self._attr_available_tones = tones
        if self.has_config(CONF_SIREN_VOLUME_DP):
            features |= SirenEntityFeature.VOLUME_SET
        if self.has_config(CONF_SIREN_DURATION_DP):
            features |= SirenEntityFeature.DURATION
        self._attr_supported_features = features

    @property
    def is_on(self):
        """Return whether the siren is active."""
        switch_dp = self._config.get(CONF_SIREN_SWITCH_DP)
        if switch_dp is not None:
            raw = self.dps(switch_dp)
            if raw == self._switch_on:
                return True
            if raw == self._switch_off:
                return False
            return None
        tone_dp = self._config.get(CONF_SIREN_TONE_DP)
        if tone_dp is not None and "off" in self._tone_values:
            return self.dps(tone_dp) != self._tone_values["off"]
        return None

    def _volume_to_raw(self, level):
        level = min(1.0, max(0.0, float(level)))
        if self._volume_values:
            closest = min(self._volume_values, key=lambda item: abs(item - level))
            return self._volume_values[closest]
        raw = self._volume_min + level * (self._volume_max - self._volume_min)
        raw = round(raw, 10)
        return int(raw) if float(raw).is_integer() else raw

    async def async_turn_on(self, **kwargs):
        """Turn on the siren with optional tone, duration and volume."""
        settings = {}
        tone_dp = self._config.get(CONF_SIREN_TONE_DP)
        tone = kwargs.get(ATTR_TONE)
        if tone_dp is not None:
            if tone is None and self._config.get(CONF_SIREN_SWITCH_DP) is None:
                current = _friendly_for_raw(self._tone_values, self.dps(tone_dp))
                if current == "off" or current is None:
                    tone = self._default_tone
            if tone is not None:
                if tone not in self._tone_values or tone == "off":
                    raise ValueError(f"Unsupported siren tone: {tone}")
                settings[tone_dp] = self._tone_values[tone]

        if kwargs.get(ATTR_DURATION) is not None:
            duration_dp = self._config.get(CONF_SIREN_DURATION_DP)
            if duration_dp is not None:
                settings[duration_dp] = _duration_to_raw(
                    kwargs[ATTR_DURATION], self._duration_scaling
                )

        if kwargs.get(ATTR_VOLUME_LEVEL) is not None:
            volume_dp = self._config.get(CONF_SIREN_VOLUME_DP)
            if volume_dp is not None:
                settings[volume_dp] = self._volume_to_raw(kwargs[ATTR_VOLUME_LEVEL])

        switch_dp = self._config.get(CONF_SIREN_SWITCH_DP)
        if switch_dp is not None and self.is_on is not True:
            settings[switch_dp] = self._switch_on

        if not settings:
            raise NotImplementedError()
        if len(settings) == 1:
            dp_id, raw = next(iter(settings.items()))
            await self._device.set_dp(raw, dp_id)
        else:
            await self._device.set_dps(settings)

    async def async_turn_off(self):
        """Turn off the siren."""
        switch_dp = self._config.get(CONF_SIREN_SWITCH_DP)
        if switch_dp is not None:
            await self._device.set_dp(self._switch_off, switch_dp)
            return
        tone_dp = self._config.get(CONF_SIREN_TONE_DP)
        if tone_dp is not None and "off" in self._tone_values:
            await self._device.set_dp(self._tone_values["off"], tone_dp)
            return
        raise NotImplementedError()


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaSiren, flow_schema)
