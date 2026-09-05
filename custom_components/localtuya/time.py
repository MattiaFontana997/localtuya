"""Platform to expose Tuya time datapoints as Home Assistant time entities."""

from datetime import time as dt_time
from functools import partial
import logging
from time import time as time

import voluptuous as vol
from homeassistant.components.time import DOMAIN, TimeEntity

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_TIME_HMS_DP,
    CONF_TIME_HMS_FORMAT,
    CONF_TIME_HOUR_DP,
    CONF_TIME_MINUTE_DP,
    CONF_TIME_SECOND_DP,
)

_LOGGER = logging.getLogger(__name__)

_TIME_FORMATS = ("hms", "hm", "compact_hms", "compact_hm")


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_TIME_HOUR_DP): vol.In(dps),
        vol.Optional(CONF_TIME_MINUTE_DP): vol.In(dps),
        vol.Optional(CONF_TIME_SECOND_DP): vol.In(dps),
        vol.Optional(CONF_TIME_HMS_DP): vol.In(dps),
        vol.Optional(CONF_TIME_HMS_FORMAT, default="hms"): vol.In(_TIME_FORMATS),
    }


def _number(value):
    """Return an integer time component when the raw value is numeric."""
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_hms(value):
    """Decode Tuya Local colon-delimited or compact time strings."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None

    try:
        if ":" in value:
            parts = value.split(":")
            if len(parts) == 2:
                hour, minute = map(int, parts)
                second = 0
            elif len(parts) == 3:
                hour, minute, second = map(int, parts)
            else:
                return None
        else:
            if not value.isdigit():
                return None
            if len(value) <= 2:
                hour, minute, second = int(value), 0, 0
            elif len(value) <= 4:
                hour, minute, second = int(value[:-2]), int(value[-2:]), 0
            else:
                hour = int(value[:-4])
                minute = int(value[-4:-2])
                second = int(value[-2:])
        return dt_time(hour, minute, second)
    except (TypeError, ValueError):
        return None


def _format_hms(value: dt_time, format_name: str) -> str:
    """Encode a Home Assistant time using the configured exact Tuya shape."""
    if format_name == "hm":
        return f"{value.hour:02d}:{value.minute:02d}"
    if format_name == "compact_hm":
        return f"{value.hour:02d}{value.minute:02d}"
    if format_name == "compact_hms":
        return f"{value.hour:02d}{value.minute:02d}{value.second:02d}"
    return f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}"


class LocaltuyaTime(LocalTuyaEntity, TimeEntity):
    """Representation of one Tuya time entity."""

    def __init__(self, device, config_entry, timeid, **kwargs):
        """Initialize the Tuya time entity."""
        super().__init__(device, config_entry, timeid, _LOGGER, **kwargs)
        self._hms_format = self._config.get(CONF_TIME_HMS_FORMAT, "hms")

    @property
    def native_value(self) -> dt_time | None:
        """Return the current time."""
        hms_dp = self._config.get(CONF_TIME_HMS_DP)
        if hms_dp is not None:
            return _parse_hms(self.dps(hms_dp))

        hour = _number(self.dps(self._config[CONF_TIME_HOUR_DP])) if self.has_config(CONF_TIME_HOUR_DP) else 0
        minute = _number(self.dps(self._config[CONF_TIME_MINUTE_DP])) if self.has_config(CONF_TIME_MINUTE_DP) else 0
        second = _number(self.dps(self._config[CONF_TIME_SECOND_DP])) if self.has_config(CONF_TIME_SECOND_DP) else 0
        if hour is None or minute is None or second is None:
            return None
        if not any(
            self.has_config(key)
            for key in (CONF_TIME_HOUR_DP, CONF_TIME_MINUTE_DP, CONF_TIME_SECOND_DP)
        ):
            return _parse_hms(self.dps(self._dp_id))

        total_seconds = hour * 3600 + minute * 60 + second
        if total_seconds < 0:
            return None
        total_seconds %= 24 * 3600
        return dt_time(
            total_seconds // 3600,
            (total_seconds // 60) % 60,
            total_seconds % 60,
        )

    async def async_set_value(self, value: dt_time) -> None:
        """Set the exact catalog-provided Tuya time representation."""
        hms_dp = self._config.get(CONF_TIME_HMS_DP)
        if hms_dp is not None:
            await self._device.set_dp(_format_hms(value, self._hms_format), hms_dp)
            return

        settings = {}
        hours = value.hour
        minutes = value.minute
        seconds = value.second

        hour_dp = self._config.get(CONF_TIME_HOUR_DP)
        if hour_dp is not None:
            settings[hour_dp] = hours
        else:
            minutes += hours * 60

        minute_dp = self._config.get(CONF_TIME_MINUTE_DP)
        if minute_dp is not None:
            settings[minute_dp] = minutes
        else:
            seconds += minutes * 60

        second_dp = self._config.get(CONF_TIME_SECOND_DP)
        if second_dp is not None:
            settings[second_dp] = seconds

        if not settings:
            await self._device.set_dp(_format_hms(value, self._hms_format), self._dp_id)
        elif len(settings) == 1:
            dp_id, raw = next(iter(settings.items()))
            await self._device.set_dp(raw, dp_id)
        else:
            await self._device.set_dps(settings)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaTime, flow_schema)
