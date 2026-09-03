"""Platform to locally control Tuya-based vacuum devices."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.vacuum import (
    DOMAIN,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_BATTERY_DP,
    CONF_CLEAN_AREA_DP,
    CONF_CLEAN_RECORD_DP,
    CONF_CLEAN_TIME_DP,
    CONF_DOCKED_STATUS_VALUE,
    CONF_FAN_SPEED_DP,
    CONF_FAN_SPEEDS,
    CONF_FAULT_DP,
    CONF_IDLE_STATUS_VALUE,
    CONF_LOCATE_DP,
    CONF_MODE_DP,
    CONF_MODES,
    CONF_PAUSED_STATE,
    CONF_POWERGO_DP,
    CONF_RETURN_MODE,
    CONF_RETURNING_STATUS_VALUE,
    CONF_STOP_STATUS,
)

_LOGGER = logging.getLogger(__name__)

CLEAN_TIME = "clean_time"
CLEAN_AREA = "clean_area"
CLEAN_RECORD = "clean_record"
MODES_LIST = "cleaning_mode_list"
MODE = "cleaning_mode"
FAULT = "fault"

# Kept as a custom attribute for backwards compatibility.
# A later mapper/sensor pass will expose it as a SensorEntity.
BATTERY_LEVEL = "battery_level"

DEFAULT_IDLE_STATUS = "standby,sleep"
DEFAULT_RETURNING_STATUS = "docking"
DEFAULT_DOCKED_STATUS = "charging,chargecompleted"
DEFAULT_MODES = "smart,wall_follow,spiral,single"
DEFAULT_FAN_SPEEDS = "low,normal,high"
DEFAULT_PAUSED_STATE = "paused"
DEFAULT_RETURN_MODE = "chargego"
DEFAULT_STOP_STATUS = "standby"


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Required(
            CONF_IDLE_STATUS_VALUE,
            default=DEFAULT_IDLE_STATUS,
        ): str,
        vol.Required(CONF_POWERGO_DP): vol.In(dps),
        vol.Required(
            CONF_DOCKED_STATUS_VALUE,
            default=DEFAULT_DOCKED_STATUS,
        ): str,
        vol.Optional(
            CONF_RETURNING_STATUS_VALUE,
            default=DEFAULT_RETURNING_STATUS,
        ): str,
        vol.Optional(CONF_BATTERY_DP): vol.In(dps),
        vol.Optional(CONF_MODE_DP): vol.In(dps),
        vol.Optional(
            CONF_MODES,
            default=DEFAULT_MODES,
        ): str,
        vol.Optional(
            CONF_RETURN_MODE,
            default=DEFAULT_RETURN_MODE,
        ): str,
        vol.Optional(CONF_FAN_SPEED_DP): vol.In(dps),
        vol.Optional(
            CONF_FAN_SPEEDS,
            default=DEFAULT_FAN_SPEEDS,
        ): str,
        vol.Optional(CONF_CLEAN_TIME_DP): vol.In(dps),
        vol.Optional(CONF_CLEAN_AREA_DP): vol.In(dps),
        vol.Optional(CONF_CLEAN_RECORD_DP): vol.In(dps),
        vol.Optional(CONF_LOCATE_DP): vol.In(dps),
        vol.Optional(CONF_FAULT_DP): vol.In(dps),
        vol.Optional(
            CONF_PAUSED_STATE,
            default=DEFAULT_PAUSED_STATE,
        ): str,
        vol.Optional(
            CONF_STOP_STATUS,
            default=DEFAULT_STOP_STATUS,
        ): str,
    }


def _split_values(value) -> list[str]:
    """Split a comma-separated Tuya configuration value."""
    return [
        item.strip()
        for item in str(value).split(",")
        if item.strip()
    ]


class LocaltuyaVacuum(LocalTuyaEntity, StateVacuumEntity):
    """Representation of a Tuya vacuum."""

    def __init__(
        self,
        device,
        config_entry,
        switchid,
        **kwargs,
    ):
        """Initialize the Tuya vacuum."""
        super().__init__(
            device,
            config_entry,
            switchid,
            _LOGGER,
            **kwargs,
        )

        self._state = None
        self._attrs = {}

        self._idle_status_list = _split_values(
            self._config.get(
                CONF_IDLE_STATUS_VALUE,
                DEFAULT_IDLE_STATUS,
            )
        )

        self._returning_status_list = _split_values(
            self._config.get(
                CONF_RETURNING_STATUS_VALUE,
                DEFAULT_RETURNING_STATUS,
            )
        )

        self._docked_status_list = _split_values(
            self._config.get(
                CONF_DOCKED_STATUS_VALUE,
                DEFAULT_DOCKED_STATUS,
            )
        )

        self._paused_status_list = _split_values(
            self._config.get(
                CONF_PAUSED_STATE,
                DEFAULT_PAUSED_STATE,
            )
        )

        self._modes_list = _split_values(
            self._config.get(
                CONF_MODES,
                DEFAULT_MODES,
            )
        )

        self._attr_fan_speed_list = _split_values(
            self._config.get(
                CONF_FAN_SPEEDS,
                DEFAULT_FAN_SPEEDS,
            )
        )

        self._attr_fan_speed = None
        self._attr_activity = None

        if self.has_config(CONF_MODE_DP) and self._modes_list:
            self._attrs[MODES_LIST] = self._modes_list

        features = (
            VacuumEntityFeature.START
            | VacuumEntityFeature.PAUSE
            | VacuumEntityFeature.STATE
        )

        if (
            self.has_config(CONF_MODE_DP)
            and self.has_config(CONF_STOP_STATUS)
        ):
            features |= VacuumEntityFeature.STOP

        if (
            self.has_config(CONF_MODE_DP)
            and self.has_config(CONF_RETURN_MODE)
        ):
            features |= VacuumEntityFeature.RETURN_HOME

        if self.has_config(CONF_FAN_SPEED_DP):
            features |= VacuumEntityFeature.FAN_SPEED

        if self.has_config(CONF_LOCATE_DP):
            features |= VacuumEntityFeature.LOCATE

        if self.has_config(CONF_MODE_DP):
            features |= VacuumEntityFeature.SEND_COMMAND

        self._attr_supported_features = features

    @property
    def extra_state_attributes(self):
        """Return LocalTuya-specific vacuum attributes."""
        return dict(self._attrs)

    async def async_start(self, **kwargs):
        """Start cleaning."""
        await self._device.set_dp(
            True,
            self._config[CONF_POWERGO_DP],
        )

    async def async_pause(self, **kwargs):
        """Pause cleaning."""
        await self._device.set_dp(
            False,
            self._config[CONF_POWERGO_DP],
        )

    async def async_return_to_base(self, **kwargs):
        """Return the vacuum to its dock."""
        if not self.has_config(CONF_MODE_DP):
            self.warning(
                "Return-to-base requested without a mode DP"
            )
            return

        await self._device.set_dp(
            self._config.get(
                CONF_RETURN_MODE,
                DEFAULT_RETURN_MODE,
            ),
            self._config[CONF_MODE_DP],
        )

    async def async_stop(self, **kwargs):
        """Stop cleaning without relying on deprecated vacuum state APIs."""
        if not self.has_config(CONF_MODE_DP):
            self.warning("Stop requested without a mode DP")
            return

        await self._device.set_dp(
            self._config.get(
                CONF_STOP_STATUS,
                DEFAULT_STOP_STATUS,
            ),
            self._config[CONF_MODE_DP],
        )

    async def async_locate(self, **kwargs):
        """Locate the vacuum."""
        if not self.has_config(CONF_LOCATE_DP):
            return

        await self._device.set_dp(
            "",
            self._config[CONF_LOCATE_DP],
        )

    async def async_set_fan_speed(
        self,
        fan_speed,
        **kwargs,
    ):
        """Set vacuum fan speed."""
        if not self.has_config(CONF_FAN_SPEED_DP):
            self.warning(
                "Fan speed requested without a fan-speed DP"
            )
            return

        if (
            self._attr_fan_speed_list
            and fan_speed not in self._attr_fan_speed_list
        ):
            self.warning(
                "Unsupported vacuum fan speed %r",
                fan_speed,
            )
            return

        await self._device.set_dp(
            fan_speed,
            self._config[CONF_FAN_SPEED_DP],
        )

    async def async_send_command(
        self,
        command,
        params=None,
        **kwargs,
    ):
        """Send an integration-specific vacuum command."""
        if command != "set_mode":
            self.warning(
                "Unsupported vacuum command %r",
                command,
            )
            return

        if not isinstance(params, dict) or "mode" not in params:
            self.warning(
                "set_mode requires params={'mode': ...}"
            )
            return

        if not self.has_config(CONF_MODE_DP):
            self.warning(
                "set_mode requested without a mode DP"
            )
            return

        mode = params["mode"]

        if self._modes_list and mode not in self._modes_list:
            self.warning(
                "Unsupported cleaning mode %r",
                mode,
            )
            return

        await self._device.set_dp(
            mode,
            self._config[CONF_MODE_DP],
        )

    def status_updated(self):
        """Update vacuum activity and attributes."""
        super().status_updated()

        raw_state = self._state

        if raw_state is None:
            self._attr_activity = None
        else:
            state_value = str(raw_state)

            if state_value in self._idle_status_list:
                self._attr_activity = VacuumActivity.IDLE

            elif state_value in self._docked_status_list:
                self._attr_activity = VacuumActivity.DOCKED

            elif state_value in self._returning_status_list:
                self._attr_activity = VacuumActivity.RETURNING

            elif state_value in self._paused_status_list:
                self._attr_activity = VacuumActivity.PAUSED

            else:
                self._attr_activity = VacuumActivity.CLEANING

        if self.has_config(CONF_BATTERY_DP):
            battery = self.dps_conf(CONF_BATTERY_DP)

            if battery is not None:
                self._attrs[BATTERY_LEVEL] = battery
            else:
                self._attrs.pop(BATTERY_LEVEL, None)

        if self.has_config(CONF_MODE_DP):
            cleaning_mode = self.dps_conf(CONF_MODE_DP)

            if cleaning_mode is not None:
                self._attrs[MODE] = cleaning_mode
            else:
                self._attrs.pop(MODE, None)

        if self.has_config(CONF_FAN_SPEED_DP):
            fan_speed = self.dps_conf(CONF_FAN_SPEED_DP)

            self._attr_fan_speed = (
                str(fan_speed)
                if fan_speed is not None
                else None
            )

        if self.has_config(CONF_CLEAN_TIME_DP):
            self._attrs[CLEAN_TIME] = self.dps_conf(
                CONF_CLEAN_TIME_DP
            )

        if self.has_config(CONF_CLEAN_AREA_DP):
            self._attrs[CLEAN_AREA] = self.dps_conf(
                CONF_CLEAN_AREA_DP
            )

        if self.has_config(CONF_CLEAN_RECORD_DP):
            self._attrs[CLEAN_RECORD] = self.dps_conf(
                CONF_CLEAN_RECORD_DP
            )

        if self.has_config(CONF_FAULT_DP):
            fault = self.dps_conf(CONF_FAULT_DP)
            self._attrs[FAULT] = fault

            if fault not in (None, 0, "0", ""):
                self._attr_activity = VacuumActivity.ERROR


async_setup_entry = partial(
    async_setup_entry,
    DOMAIN,
    LocaltuyaVacuum,
    flow_schema,
)
