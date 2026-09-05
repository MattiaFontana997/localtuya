"""Platform to locally control Tuya time datapoints."""

import logging
from datetime import time
from functools import partial

import voluptuous as vol
from homeassistant.components.time import DOMAIN, TimeEntity

from .common import LocalTuyaEntity, async_setup_entry
from .const import CONF_TIME_HMS_DP, CONF_TIME_HOUR_DP, CONF_TIME_MINUTE_DP, CONF_TIME_SECOND_DP

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_TIME_HOUR_DP): vol.In(dps),
        vol.Optional(CONF_TIME_MINUTE_DP): vol.In(dps),
        vol.Optional(CONF_TIME_SECOND_DP): vol.In(dps),
        vol.Optional(CONF_TIME_HMS_DP): vol.In(dps),
    }


def _parse_hms(value):
    if not isinstance(value, str) or not value:
        return None
    parts = value.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]), int(parts[1]), int(parts[2])
        if len(parts) == 2:
            return int(parts[0]), int(parts[1]), 0
        if len(parts) == 1:
            raw = parts[0]
            if len(raw) <= 2:
                return int(raw), 0, 0
            if len(raw) <= 4:
                return int(raw[:-2]), int(raw[-2:]), 0
            return int(raw[:-4]), int(raw[-4:-2]), int(raw[-2:])
    except ValueError:
        return None
    return None


class LocaltuyaTime(LocalTuyaEntity, TimeEntity):
    """Representation of a Tuya time entity."""

    @property
    def native_value(self):
        hours = minutes = seconds = None
        if self.has_config(CONF_TIME_HOUR_DP):
            hours = self.dps(self._config[CONF_TIME_HOUR_DP])
        if self.has_config(CONF_TIME_MINUTE_DP):
            minutes = self.dps(self._config[CONF_TIME_MINUTE_DP])
        if self.has_config(CONF_TIME_SECOND_DP):
            seconds = self.dps(self._config[CONF_TIME_SECOND_DP])
        if self.has_config(CONF_TIME_HMS_DP):
            parsed = _parse_hms(self.dps(self._config[CONF_TIME_HMS_DP]))
            if parsed is not None:
                hours, minutes, seconds = parsed
        if hours is None and minutes is None and seconds is None:
            return None
        try:
            total = (int(hours or 0) * 3600 + int(minutes or 0) * 60 + int(seconds or 0)) % 86400
        except (TypeError, ValueError):
            return None
        return time(total // 3600, (total % 3600) // 60, total % 60)

    async def async_set_value(self, value: time) -> None:
        settings = {}
        hours = value.hour
        minutes = value.minute
        seconds = value.second
        if self.has_config(CONF_TIME_HOUR_DP):
            settings[self._config[CONF_TIME_HOUR_DP]] = hours
        else:
            minutes += hours * 60
        if self.has_config(CONF_TIME_MINUTE_DP):
            settings[self._config[CONF_TIME_MINUTE_DP]] = minutes
        else:
            seconds += minutes * 60
        if self.has_config(CONF_TIME_SECOND_DP):
            settings[self._config[CONF_TIME_SECOND_DP]] = seconds
        if not settings and self.has_config(CONF_TIME_HMS_DP):
            settings[self._config[CONF_TIME_HMS_DP]] = value.strftime("%H:%M:%S")
        if not settings:
            raise NotImplementedError()
        await self._device.set_dps(settings)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaTime, flow_schema)
