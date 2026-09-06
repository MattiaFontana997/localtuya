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
from .fan_mapping import (
    RAW_TYPES as FAN_RAW_TYPES,
    coerce_fan_raw,
    fan_oscillation_from_raw,
    fan_oscillation_to_raw,
    fan_speed_from_raw,
    fan_speed_to_raw,
    validate_fan_oscillation_mapping,
    validate_fan_speed_mapping,
)
from .const import (
    CONF_FAN_DIRECTION,
    CONF_FAN_DIRECTION_FWD,
    CONF_FAN_DIRECTION_REV,
    CONF_FAN_DPS_TYPE,
    CONF_FAN_ORDERED_LIST,
    CONF_FAN_OSCILLATING_CONTROL,
    CONF_FAN_OSCILLATING_OFF,
    CONF_FAN_OSCILLATING_ON,
    CONF_FAN_PRESET_DEFAULT,
    CONF_FAN_PRESET_DP,
    CONF_FAN_PRESET_VALUES,
    CONF_FAN_NO_SWITCH,
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
        vol.Optional(CONF_FAN_NO_SWITCH, default=False): bool,
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
        self._attr_preset_mode = None

        self._preset_raw_type = self._config.get("fan_preset_raw_type", "string")
        if self._preset_raw_type not in FAN_RAW_TYPES:
            self.warning("Invalid fan preset raw type %r; disabling presets", self._preset_raw_type)
            self._preset_raw_type = "string"
        self._speed_mapping = validate_fan_speed_mapping(
            self._config.get("fan_speed_mapping")
        )
        self._oscillation_mapping = validate_fan_oscillation_mapping(
            self._config.get("fan_oscillating_mapping")
        )
        self._preset_values = self._configured_preset_values()
        self._preset_default = self._config.get(CONF_FAN_PRESET_DEFAULT)
        if self._preset_default not in self._preset_values:
            self._preset_default = None
        self._preset_raw_to_name = {
            raw: name for name, raw in self._preset_values.items()
        }
        self._no_switch = self._config.get(CONF_FAN_NO_SWITCH) is True
        self._attr_preset_modes = (
            list(self._preset_values) if self._preset_values else None
        )
        self._oscillating_on = self._config.get(
            CONF_FAN_OSCILLATING_ON, True
        )
        self._oscillating_off = self._config.get(
            CONF_FAN_OSCILLATING_OFF, False
        )

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

        features = FanEntityFeature(0)
        if not self._no_switch:
            features |= FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

        if self.has_config(CONF_FAN_SPEED_CONTROL):
            features |= FanEntityFeature.SET_SPEED

        if self.has_config(CONF_FAN_OSCILLATING_CONTROL):
            features |= FanEntityFeature.OSCILLATE

        if self.has_config(CONF_FAN_DIRECTION):
            features |= FanEntityFeature.DIRECTION

        if self.has_config(CONF_FAN_PRESET_DP) and self._preset_values:
            features |= FanEntityFeature.PRESET_MODE

        self._attr_supported_features = features

        if self.has_config(CONF_FAN_SPEED_CONTROL):
            if self._speed_mapping:
                self._attr_speed_count = len(self._speed_mapping["rules"])
            elif self._use_ordered_list:
                self._attr_speed_count = len(self._ordered_list)
            else:
                self._attr_speed_count = int_states_in_range(
                    self._speed_range
                )

    def _configured_preset_values(self) -> dict[str, object]:
        """Return validated friendly -> typed raw fan presets."""
        configured = self._config.get(CONF_FAN_PRESET_VALUES)
        if configured is None:
            return {}
        if not isinstance(configured, dict):
            self.warning("Invalid fan_preset_values config; ignoring presets")
            return {}

        raw_type = getattr(
            self,
            "_preset_raw_type",
            self._config.get("fan_preset_raw_type", "string"),
        )
        if raw_type not in FAN_RAW_TYPES:
            raw_type = "string"

        result: dict[str, object] = {}
        raw_values: list[object] = []
        for name, raw in configured.items():
            if not isinstance(name, str) or not name.strip():
                self.warning("Ignoring invalid fan preset %r: %r", name, raw)
                continue
            try:
                raw = coerce_fan_raw(raw, raw_type)
            except ValueError:
                self.warning("Ignoring invalid fan preset %r: %r", name, raw)
                continue
            name = name.strip()
            if name in result or any(raw == previous for previous in raw_values):
                self.warning("Ignoring duplicate fan preset %r: %r", name, raw)
                continue
            result[name] = raw
            raw_values.append(raw)
        return result

    def _refresh_speed_count(self) -> None:
        """Refresh speed count from active declarative step metadata."""
        if not self.has_config(CONF_FAN_SPEED_CONTROL):
            return
        if self._speed_mapping:
            self._attr_speed_count = len(self._speed_mapping["rules"])
            return
        if self._use_ordered_list:
            self._attr_speed_count = len(self._ordered_list)
            return
        metadata = self.mapped_numeric_metadata(self._config[CONF_FAN_SPEED_CONTROL])
        step = metadata.get("step")
        if isinstance(step, (int, float)) and not isinstance(step, bool) and step > 0:
            self._attr_speed_count = max(1, int(round(float(self._speed_range[1]) / float(step))))
            return
        self._attr_speed_count = int_states_in_range(self._speed_range)

    @property
    def is_on(self) -> bool | None:
        """Return whether the Tuya fan is on."""
        return self._is_on

    def _percentage_to_raw(self, percentage: int):
        """Convert an HA percentage to the configured Tuya speed."""
        percentage = min(max(int(percentage), 1), 100)

        if self._speed_mapping:
            return fan_speed_to_raw(percentage, self._speed_mapping)

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
            if self._speed_mapping:
                return fan_speed_from_raw(raw_value, self._speed_mapping)

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
        states = {} if self._no_switch else {self._dp_id: True}

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

        if preset_mode is not None and self.has_config(CONF_FAN_PRESET_DP):
            raw_preset = self._preset_values.get(preset_mode)
            if raw_preset is None:
                self.warning("Unsupported fan preset %r", preset_mode)
            else:
                states[self._config[CONF_FAN_PRESET_DP]] = raw_preset

        if any(self.has_advanced_mapping(dp) for dp in states):
            await self.set_mapped_dps(states)
        else:
            await self._device.set_dps(states)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        if self._no_switch:
            raise NotImplementedError("This fan has no power control")
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

        if self.is_on is not True and not self._no_switch:
            states[self._dp_id] = True

        if any(self.has_advanced_mapping(dp) for dp in states):
            await self.set_mapped_dps(states)
        else:
            await self._device.set_dps(states)

    async def async_oscillate(
        self,
        oscillating: bool,
    ) -> None:
        """Set fan oscillation."""
        if not self.has_config(CONF_FAN_OSCILLATING_CONTROL):
            return

        oscillation_mapping = getattr(self, "_oscillation_mapping", None)
        raw_value = (
            fan_oscillation_to_raw(oscillating, oscillation_mapping)
            if oscillation_mapping
            else (self._oscillating_on if oscillating else self._oscillating_off)
        )
        await self._device.set_dp(
            raw_value,
            self._config[CONF_FAN_OSCILLATING_CONTROL],
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set a catalog-provided Tuya fan preset."""
        if not self.has_config(CONF_FAN_PRESET_DP):
            return
        raw = self._preset_values.get(preset_mode)
        if raw is None:
            self.warning("Unsupported fan preset %r", preset_mode)
            return
        await self._device.set_dp(raw, self._config[CONF_FAN_PRESET_DP])

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

        if self._no_switch:
            # Tuya Local models a fan without a switch as on whenever its
            # entity is available; HA availability already gates visibility.
            self._is_on = True
        elif isinstance(raw_power, bool):
            self._is_on = raw_power
        elif raw_power in (0, 1):
            self._is_on = bool(raw_power)
        else:
            self._is_on = None

        if self.has_config(CONF_FAN_SPEED_CONTROL):
            self._attr_percentage = self._raw_to_percentage(
                self.dps_conf(CONF_FAN_SPEED_CONTROL)
            )
            self._refresh_speed_count()
        else:
            self._attr_percentage = None

        if self.has_config(CONF_FAN_OSCILLATING_CONTROL):
            value = self.dps_conf(CONF_FAN_OSCILLATING_CONTROL)
            oscillation_mapping = getattr(self, "_oscillation_mapping", None)
            if oscillation_mapping:
                self._attr_oscillating = fan_oscillation_from_raw(
                    value, oscillation_mapping
                )
            elif value == self._oscillating_on:
                self._attr_oscillating = True
            elif value == self._oscillating_off:
                self._attr_oscillating = False
            else:
                self._attr_oscillating = None

        if self.has_config(CONF_FAN_PRESET_DP):
            raw_preset = self.dps_conf(CONF_FAN_PRESET_DP)
            self._attr_preset_mode = self._preset_raw_to_name.get(
                raw_preset, self._preset_default
            )
        else:
            self._attr_preset_mode = None

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
