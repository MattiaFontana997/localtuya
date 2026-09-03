"""Platform to present any Tuya DP as a number."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.number import (
    DOMAIN,
    NumberDeviceClass,
    NumberEntity,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_DEFAULT_VALUE,
    CONF_MAX_VALUE,
    CONF_MIN_VALUE,
    CONF_PASSIVE_ENTITY,
    CONF_RESTORE_ON_RECONNECT,
    CONF_SCALING,
    CONF_STEPSIZE_VALUE,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_MIN = 0.0
DEFAULT_MAX = 100000.0
DEFAULT_STEP = 1.0


def _scale_number_value(
    value,
    scaling: float,
) -> float:
    """Convert a raw Tuya number to its native HA value."""
    return float(value) * scaling


def _unscale_number_value(
    value,
    scaling: float,
):
    """Convert a native HA number back to its raw Tuya value."""
    raw_value = float(value) / scaling

    # Avoid values such as 224.99999999997 for Integer DPS.
    raw_value = round(
        raw_value,
        10,
    )

    if float(raw_value).is_integer():
        return int(raw_value)

    return raw_value


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_MIN_VALUE, default=DEFAULT_MIN): vol.All(
            vol.Coerce(float),
            vol.Range(min=-1000000.0, max=1000000.0),
        ),
        vol.Required(CONF_MAX_VALUE, default=DEFAULT_MAX): vol.All(
            vol.Coerce(float),
            vol.Range(min=-1000000.0, max=1000000.0),
        ),
        vol.Required(CONF_STEPSIZE_VALUE, default=DEFAULT_STEP): vol.All(
            vol.Coerce(float),
            vol.Range(min=0.0, max=1000000.0),
        ),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): str,
        vol.Optional(
            CONF_SCALING,
            default=1.0,
        ): vol.All(
            vol.Coerce(float),
            vol.Range(
                min=0.000000001,
                max=1000000000.0,
            ),
        ),
        vol.Optional(CONF_DEVICE_CLASS): vol.In(
            [device_class.value for device_class in NumberDeviceClass]
        ),
        vol.Required(CONF_RESTORE_ON_RECONNECT): bool,
        vol.Required(CONF_PASSIVE_ENTITY): bool,
        vol.Optional(CONF_DEFAULT_VALUE): str,
    }


class LocaltuyaNumber(LocalTuyaEntity, NumberEntity):
    """Representation of a Tuya number."""

    def __init__(
        self,
        device,
        config_entry,
        sensorid,
        **kwargs,
    ):
        """Initialize the Tuya number."""
        super().__init__(device, config_entry, sensorid, _LOGGER, **kwargs)

        self._state = None

        self._scaling = float(
            self._config.get(
                CONF_SCALING,
                1.0,
            )
        )

        if self._scaling <= 0:
            raise ValueError(
                "Number scaling must be greater than zero"
            )

        self._attr_native_min_value = float(
            self._config.get(CONF_MIN_VALUE, DEFAULT_MIN)
        )
        self._attr_native_max_value = float(
            self._config.get(CONF_MAX_VALUE, DEFAULT_MAX)
        )
        self._attr_native_step = float(
            self._config.get(CONF_STEPSIZE_VALUE, DEFAULT_STEP)
        )
        self._attr_native_unit_of_measurement = self._config.get(
            CONF_UNIT_OF_MEASUREMENT
        )

        device_class = self._config.get(CONF_DEVICE_CLASS)
        self._attr_device_class = (
            NumberDeviceClass(device_class)
            if device_class
            else None
        )

        default_value = self._config.get(CONF_DEFAULT_VALUE)
        if default_value is not None:
            self._default_value = float(default_value)

    @property
    def native_value(self) -> float | None:
        """Return the native number value."""
        return self._state

    def status_updated(self):
        """Update the number value from the Tuya DP."""
        raw_state = self.dps(self._dp_id)

        if raw_state is None or isinstance(raw_state, bool):
            self._state = None
            return

        try:
            value = float(raw_state)
        except (TypeError, ValueError):
            self._state = None
            self.warning(
                "Number entity %s received non-numeric value %r",
                self.entity_id,
                raw_state,
            )
            return

        self._state = _scale_number_value(
            value,
            self._scaling,
        )

        if not self._device.is_connecting:
            self._last_state = self._state

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        raw_value = _unscale_number_value(
            value,
            self._scaling,
        )

        await self._device.set_dp(
            raw_value,
            self._dp_id,
        )

    def entity_default_value(self):
        """Return the minimum value as the default value."""
        return self._attr_native_min_value


async_setup_entry = partial(
    async_setup_entry,
    DOMAIN,
    LocaltuyaNumber,
    flow_schema,
)
