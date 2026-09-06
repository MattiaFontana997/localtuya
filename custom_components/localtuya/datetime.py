"""Platform to expose Tuya datetime datapoints as Home Assistant datetimes."""

from datetime import datetime, timezone
import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.datetime import DOMAIN, DateTimeEntity

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_DATETIME_DAY_DP,
    CONF_DATETIME_HOUR_DP,
    CONF_DATETIME_MINUTE_DP,
    CONF_DATETIME_MONTH_DP,
    CONF_DATETIME_SECOND_DP,
    CONF_DATETIME_TIMESTAMP_DP,
    CONF_DATETIME_TIMESTAMP_SCALING,
    CONF_DATETIME_TIMEZONE,
    CONF_DATETIME_YEAR_DP,
)

_LOGGER = logging.getLogger(__name__)

_COMPONENT_KEYS = (
    CONF_DATETIME_YEAR_DP,
    CONF_DATETIME_MONTH_DP,
    CONF_DATETIME_DAY_DP,
    CONF_DATETIME_HOUR_DP,
    CONF_DATETIME_MINUTE_DP,
    CONF_DATETIME_SECOND_DP,
)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_DATETIME_TIMESTAMP_DP): vol.In(dps),
        vol.Optional(CONF_DATETIME_YEAR_DP): vol.In(dps),
        vol.Optional(CONF_DATETIME_MONTH_DP): vol.In(dps),
        vol.Optional(CONF_DATETIME_DAY_DP): vol.In(dps),
        vol.Optional(CONF_DATETIME_HOUR_DP): vol.In(dps),
        vol.Optional(CONF_DATETIME_MINUTE_DP): vol.In(dps),
        vol.Optional(CONF_DATETIME_SECOND_DP): vol.In(dps),
        vol.Optional(CONF_DATETIME_TIMESTAMP_SCALING, default=1.0): vol.Coerce(float),
        vol.Optional(CONF_DATETIME_TIMEZONE, default="utc"): vol.In(("utc", "local")),
    }


def _numeric(value):
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value, default):
    if value is None or isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _timezone_for(mode):
    if mode == "local":
        return datetime.now().astimezone().tzinfo or timezone.utc
    return timezone.utc


def _ensure_aware(value):
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class LocaltuyaDateTime(LocalTuyaEntity, DateTimeEntity):
    """Representation of a Tuya datetime."""

    def __init__(self, device, config_entry, datetimeid, **kwargs):
        """Initialize the Tuya datetime entity."""
        super().__init__(device, config_entry, datetimeid, _LOGGER, **kwargs)
        self._timestamp_scaling = float(
            self._config.get(CONF_DATETIME_TIMESTAMP_SCALING, 1.0)
        )
        if self._timestamp_scaling <= 0:
            raise ValueError("Datetime timestamp scaling must be greater than zero")
        self._timezone_mode = self._config.get(CONF_DATETIME_TIMEZONE, "utc")

    def _uses_components(self):
        return any(self.has_config(key) for key in _COMPONENT_KEYS)

    @property
    def native_value(self):
        """Return the current datetime as a timezone-aware value."""
        if not self._uses_components():
            dp_id = self._config.get(CONF_DATETIME_TIMESTAMP_DP, self._dp_id)
            raw = _numeric(self.dps(dp_id))
            if raw is None:
                return None
            try:
                value = datetime.fromtimestamp(
                    raw * self._timestamp_scaling,
                    timezone.utc,
                )
            except (OverflowError, OSError, ValueError):
                return None
            if self._timezone_mode == "local":
                return value.astimezone(_timezone_for("local"))
            return value

        tz = _timezone_for(self._timezone_mode)
        values = {
            CONF_DATETIME_YEAR_DP: 1970,
            CONF_DATETIME_MONTH_DP: 1,
            CONF_DATETIME_DAY_DP: 1,
            CONF_DATETIME_HOUR_DP: 0,
            CONF_DATETIME_MINUTE_DP: 0,
            CONF_DATETIME_SECOND_DP: 0,
        }
        for key, default in tuple(values.items()):
            if self.has_config(key):
                values[key] = _integer(self.dps(self._config[key]), default)

        try:
            return datetime(
                values[CONF_DATETIME_YEAR_DP],
                values[CONF_DATETIME_MONTH_DP],
                values[CONF_DATETIME_DAY_DP],
                values[CONF_DATETIME_HOUR_DP],
                values[CONF_DATETIME_MINUTE_DP],
                values[CONF_DATETIME_SECOND_DP],
                tzinfo=tz,
            )
        except ValueError:
            return None

    async def async_set_value(self, value: datetime):
        """Write a datetime using the exact catalog representation."""
        value = _ensure_aware(value)

        if not self._uses_components():
            dp_id = self._config.get(CONF_DATETIME_TIMESTAMP_DP, self._dp_id)
            raw = round(value.astimezone(timezone.utc).timestamp() / self._timestamp_scaling, 10)
            raw = int(raw) if float(raw).is_integer() else raw
            await self._device.set_dp(raw, dp_id)
            return

        target_tz = _timezone_for(self._timezone_mode)
        value = value.astimezone(target_tz)
        raw_values = {
            CONF_DATETIME_YEAR_DP: value.year,
            CONF_DATETIME_MONTH_DP: value.month,
            CONF_DATETIME_DAY_DP: value.day,
            CONF_DATETIME_HOUR_DP: value.hour,
            CONF_DATETIME_MINUTE_DP: value.minute,
            CONF_DATETIME_SECOND_DP: value.second,
        }
        settings = {
            self._config[key]: raw
            for key, raw in raw_values.items()
            if self.has_config(key)
        }
        if not settings:
            raise NotImplementedError()
        if len(settings) == 1:
            dp_id, raw = next(iter(settings.items()))
            await self._device.set_dp(raw, dp_id)
        else:
            await self._device.set_dps(settings)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaDateTime, flow_schema)
