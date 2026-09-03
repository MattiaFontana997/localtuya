"""Platform to locally control Tuya-based fan devices."""

import logging
import math
from functools import partial

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.util.percentage import (
    int_states_in_range,
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_FAN_DIRECTION,
    CONF_FAN_DIRECTION_FWD,
    CONF_FAN_DIRECTION_REV,
    CONF_FAN_DPS_TYPE,
    CONF_FAN_ORDERED_LIST,
    CONF_FAN_OSCILLATING_CONTROL,
    CONF_FAN_SPEED_CONTROL,
    CONF_FAN_SPEED_MAX,
    CONF_FAN_SPEED_MIN,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_SPEED_MIN = 1
DEFAULT_SPEED_MAX = 9


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_FAN_SPEED_CONTROL): vol.In(dps),
        vol.Optional(CONF_FAN_OSCILLATING_CONTROL): vol.In(dps),
        vol.Optional(CONF_FAN_DIRECTION): vol.In(dps),
        vol.Optional(
            CONF_FAN_DIRECTION_FWD,
            default=DIRECTION_FORWARD,
        ): cv.string,
        vol.Optional(
            CONF_FAN_DIRECTION_REV,
            default=DIRECTION_REVERSE,
        ): cv.string,
        vol.Optional(
            CONF_FAN_SPEED_MIN,
            default=DEFAULT_SPEED_MIN,
        ): cv.positive_int,
        vol.Optional(
            CONF_FAN_SPEED_MAX,
            default=DEFAULT_SPEED_MAX,
        ): cv.positive_int,
        vol.Optional(
            CONF_FAN_ORDERED_LIST,
            default="disabled",
        ): cv.string,
        vol.Optional(
            CONF_FAN_DPS_TYPE,
            default="str",
        ): vol.In(["str", "int"]),
    }


class LocaltuyaFan(LocalTuyaEntity, FanEntity):
    """Representation of a Tuya fan."""

    def __init__(
        self,
        device,
        config_entry,
        fanid,
        **kwargs,
    ):
        """Initialize the Tuya fan."""
        super().__init__(
            device,
            config_entry,
            fanid,
            _LOGGER,
            **kwargs,
        )

        self._state = None
        self._is_on = None

        self._attr_percentage = None
        self._attr_oscillating = None
        self._attr_current_direction = None

        speed_min = int(
            self._config.get(
                CONF_FAN_SPEED_MIN,
                DEFAULT_SPEED_MIN,
            )
        )
        speed_max = int(
            self._config.get(
                CONF_FAN_SPEED_MAX,
                DEFAULT_SPEED_MAX,
            )
        )

        if speed_min > speed_max:
            self.warning(
                "Fan speed range is reversed (%s..%s); normalizing it",
                speed_min,
                speed_max,
            )
            speed_min, speed_max = speed_max, speed_min

        if speed_min == speed_max:
            speed_max = speed_min + 1

        self._speed_range = (
            speed_min,
            speed_max,
        )

        ordered_list = self._config.get(
            CONF_FAN_ORDERED_LIST,
            "disabled",
        )

        self._ordered_list = [
            item.strip()
            for item in str(ordered_list).split(",")
            if item.strip()
        ]

        self._use_ordered_list = (
            len(self._ordered_list) > 1
            and self._ordered_list != ["disabled"]
        )

        self._dps_type = (
            int
            if self._config.get(CONF_FAN_DPS_TYPE) == "int"
            else str
        )

        features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

        if self.has_config(CONF_FAN_SPEED_CONTROL):
            features |= FanEntityFeature.SET_SPEED

        if self.has_config(CONF_FAN_OSCILLATING_CONTROL):
            features |= FanEntityFeature.OSCILLATE

        if self.has_config(CONF_FAN_DIRECTION):
            features |= FanEntityFeature.DIRECTION

        self._attr_supported_features = features

        if self.has_config(CONF_FAN_SPEED_CONTROL):
            if self._use_ordered_list:
                self._attr_speed_count = len(self._ordered_list)
            else:
                self._attr_speed_count = int_states_in_range(
                    self._speed_range
                )

    @property
    def is_on(self) -> bool | None:
        """Return whether the Tuya fan is on."""
        return self._is_on

    def _percentage_to_raw(self, percentage: int):
        """Convert an HA percentage to the configured Tuya speed."""
        percentage = min(max(int(percentage), 1), 100)

        if self._use_ordered_list:
            raw_value = percentage_to_ordered_list_item(
                self._ordered_list,
                percentage,
            )
            return self._dps_type(raw_value)

        raw_value = math.ceil(
            percentage_to_ranged_value(
                self._speed_range,
                percentage,
            )
        )

        raw_value = min(
            max(raw_value, self._speed_range[0]),
            self._speed_range[1],
        )

        return self._dps_type(raw_value)

    def _raw_to_percentage(self, raw_value) -> int | None:
        """Convert a Tuya fan speed into an HA percentage."""
        if raw_value is None:
            return None

        try:
            if self._use_ordered_list:
                return ordered_list_item_to_percentage(
                    self._ordered_list,
                    str(raw_value),
                )

            return ranged_value_to_percentage(
                self._speed_range,
                int(raw_value),
            )

        except (TypeError, ValueError):
            self.warning(
                "Unable to map fan speed value %r",
                raw_value,
            )
            return None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        states = {
            self._dp_id: True,
        }

        if (
            percentage is not None
            and self.has_config(CONF_FAN_SPEED_CONTROL)
        ):
            if percentage <= 0:
                await self.async_turn_off()
                return

            states[self._config[CONF_FAN_SPEED_CONTROL]] = (
                self._percentage_to_raw(percentage)
            )

        await self._device.set_dps(states)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        await self._device.set_dp(
            False,
            self._dp_id,
        )

    async def async_set_percentage(
        self,
        percentage: int,
    ) -> None:
        """Set the fan speed percentage."""
        percentage = min(max(int(percentage), 0), 100)

        if percentage == 0:
            await self.async_turn_off()
            return

        if not self.has_config(CONF_FAN_SPEED_CONTROL):
            self.warning(
                "Fan %s has no configured speed DP",
                self.entity_id,
            )
            return

        states = {
            self._config[CONF_FAN_SPEED_CONTROL]:
                self._percentage_to_raw(percentage),
        }

        if self.is_on is not True:
            states[self._dp_id] = True

        await self._device.set_dps(states)

    async def async_oscillate(
        self,
        oscillating: bool,
    ) -> None:
        """Set fan oscillation."""
        if not self.has_config(CONF_FAN_OSCILLATING_CONTROL):
            return

        await self._device.set_dp(
            bool(oscillating),
            self._config[CONF_FAN_OSCILLATING_CONTROL],
        )

    async def async_set_direction(
        self,
        direction: str,
    ) -> None:
        """Set the fan direction."""
        if not self.has_config(CONF_FAN_DIRECTION):
            return

        if direction == DIRECTION_FORWARD:
            value = self._config.get(
                CONF_FAN_DIRECTION_FWD,
                DIRECTION_FORWARD,
            )
        elif direction == DIRECTION_REVERSE:
            value = self._config.get(
                CONF_FAN_DIRECTION_REV,
                DIRECTION_REVERSE,
            )
        else:
            self.warning(
                "Unsupported fan direction %r",
                direction,
            )
            return

        await self._device.set_dp(
            value,
            self._config[CONF_FAN_DIRECTION],
        )

    def status_updated(self):
        """Update fan state from the latest Tuya status."""
        super().status_updated()

        raw_power = self._state

        if isinstance(raw_power, bool):
            self._is_on = raw_power
        elif raw_power in (0, 1):
            self._is_on = bool(raw_power)
        else:
            self._is_on = None

        if self.has_config(CONF_FAN_SPEED_CONTROL):
            self._attr_percentage = self._raw_to_percentage(
                self.dps_conf(CONF_FAN_SPEED_CONTROL)
            )
        else:
            self._attr_percentage = None

        if self.has_config(CONF_FAN_OSCILLATING_CONTROL):
            value = self.dps_conf(
                CONF_FAN_OSCILLATING_CONTROL
            )

            if isinstance(value, bool):
                self._attr_oscillating = value
            elif value in (0, 1):
                self._attr_oscillating = bool(value)
            else:
                self._attr_oscillating = None

        if self.has_config(CONF_FAN_DIRECTION):
            value = self.dps_conf(CONF_FAN_DIRECTION)

            if value == self._config.get(
                CONF_FAN_DIRECTION_FWD,
                DIRECTION_FORWARD,
            ):
                self._attr_current_direction = DIRECTION_FORWARD

            elif value == self._config.get(
                CONF_FAN_DIRECTION_REV,
                DIRECTION_REVERSE,
            ):
                self._attr_current_direction = DIRECTION_REVERSE

            else:
                self._attr_current_direction = None

    def entity_default_value(self):
        """Return the default fan power value."""
        return False


async_setup_entry = partial(
    async_setup_entry,
    DOMAIN,
    LocaltuyaFan,
    flow_schema,
)
