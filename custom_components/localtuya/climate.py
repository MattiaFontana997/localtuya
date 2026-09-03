"""Platform to locally control Tuya-based climate devices."""
import asyncio
import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.climate import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    HVACAction,
    HVACMode,
    PRESET_AWAY,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
    PRESET_BOOST,
    ClimateEntityFeature,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_TOP,
    SWING_ON,
    SWING_OFF,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_TEMPERATURE_UNIT,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    UnitOfTemperature,
)

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_CURRENT_TEMPERATURE_DP,
    CONF_TEMP_MAX,
    CONF_TEMP_MIN,
    CONF_ECO_DP,
    CONF_ECO_VALUE,
    CONF_HEURISTIC_ACTION,
    CONF_HVAC_ACTION_DP,
    CONF_HVAC_ACTION_SET,
    CONF_HVAC_MODE_DP,
    CONF_HVAC_MODE_SET,
    CONF_MAX_TEMP_DP,
    CONF_MIN_TEMP_DP,
    CONF_PRECISION,
    CONF_PRESET_DP,
    CONF_PRESET_SET,
    CONF_TARGET_PRECISION,
    CONF_TARGET_TEMPERATURE_DP,
    CONF_TEMPERATURE_STEP,
    CONF_HVAC_FAN_MODE_DP,
    CONF_HVAC_FAN_MODE_SET,
    CONF_HVAC_SWING_MODE_DP,
    CONF_HVAC_SWING_MODE_SET,
)

_LOGGER = logging.getLogger(__name__)

HVAC_MODE_SETS = {
    "manual/auto": {
        HVACMode.HEAT: "manual",
        HVACMode.AUTO: "auto",
    },
    "Manual/Auto": {
        HVACMode.HEAT: "Manual",
        HVACMode.AUTO: "Auto",
    },
    "MANUAL/AUTO": {
        HVACMode.HEAT: "MANUAL",
        HVACMode.AUTO: "AUTO",
    },
    "Manual/Program": {
        HVACMode.HEAT: "Manual",
        HVACMode.AUTO: "Program",
    },
    "m/p": {
        HVACMode.HEAT: "m",
        HVACMode.AUTO: "p",
    },
    "True/False": {
        HVACMode.HEAT: True,
    },
    "Auto/Cold/Dry/Wind/Hot": {
        HVACMode.HEAT: "hot",
        HVACMode.FAN_ONLY: "wind",
        HVACMode.DRY: "wet",
        HVACMode.COOL: "cold",
        HVACMode.AUTO: "auto",
    },
    "Cold/Dehumidify/Hot": {
        HVACMode.HEAT: "hot",
        HVACMode.DRY: "dehumidify",
        HVACMode.COOL: "cold",
    },
    "1/0": {
        HVACMode.HEAT: "1",
        HVACMode.AUTO: "0",
    },
    "heatcool_heat/heatcool_cool/heatcool_heatcool":{
        HVACMode.HEAT: "heatcool_heat",
        HVACMode.COOL: "heatcool_cool",
        HVACMode.HEAT_COOL: "heatcool_heatcool",
    },
}
HVAC_ACTION_SETS = {
    "True/False": {
        HVACAction.HEATING: True,
        HVACAction.IDLE: False,
    },
    "open/close": {
        HVACAction.HEATING: "open",
        HVACAction.IDLE: "close",
    },
    "heating/no_heating": {
        HVACAction.HEATING: "heating",
        HVACAction.IDLE: "no_heating",
    },
    "Heat/Warming": {
        HVACAction.HEATING: "Heat",
        HVACAction.IDLE: "Warming",
    },
    "heating/warming": {
        HVACAction.HEATING: "heating",
        HVACAction.IDLE: "warming",
    },
    "heat/cool/idle": {
        HVACAction.HEATING: "heat",
        HVACAction.COOLING: "cool",
        HVACAction.IDLE: "off",
    }
}
HVAC_FAN_MODE_SETS = {
    "Auto/Low/Middle/High/Strong": {
        FAN_AUTO: "auto",
        FAN_LOW: "low",
        FAN_MEDIUM: "middle",
        FAN_HIGH: "high",
        FAN_TOP: "strong",
    }
}
HVAC_SWING_MODE_SETS = {
    "True/False": {
        SWING_ON: True,
        SWING_OFF: False,
    }
}
PRESET_SETS = {
    "Manual/Holiday/Program": {
        PRESET_AWAY: "Holiday",
        PRESET_HOME: "Program",
        PRESET_NONE: "Manual",
    },
    "smart/holiday/hold": {
        PRESET_AWAY: "holiday",
        PRESET_HOME: "smart",
        PRESET_NONE: "hold",
    },
    "auto/manual/temporary/boost/holiday": {
        PRESET_AWAY: 'holiday',
        PRESET_HOME: 'manual',
        PRESET_BOOST: 'boost',
        PRESET_NONE: 'auto'
    }
}

TEMPERATURE_CELSIUS = "celsius"
TEMPERATURE_FAHRENHEIT = "fahrenheit"
DEFAULT_TEMPERATURE_UNIT = TEMPERATURE_CELSIUS
DEFAULT_PRECISION = PRECISION_TENTHS
DEFAULT_TEMPERATURE_STEP = PRECISION_HALVES
# Empirically tested to work for AVATTO thermostat
MODE_WAIT = 0.1


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_TARGET_TEMPERATURE_DP): vol.In(dps),
        vol.Optional(CONF_CURRENT_TEMPERATURE_DP): vol.In(dps),
        vol.Optional(CONF_TEMPERATURE_STEP, default=PRECISION_WHOLE): vol.In(
            [PRECISION_WHOLE, PRECISION_HALVES, PRECISION_TENTHS]
        ),
        vol.Optional(CONF_TEMP_MIN, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_TEMP_MAX, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP_DP): vol.In(dps),
        vol.Optional(CONF_MIN_TEMP_DP): vol.In(dps),
        vol.Optional(CONF_PRECISION, default=PRECISION_WHOLE): vol.In(
            [PRECISION_WHOLE, PRECISION_HALVES, PRECISION_TENTHS]
        ),
        vol.Optional(CONF_HVAC_MODE_DP): vol.In(dps),
        vol.Optional(CONF_HVAC_MODE_SET): vol.In(list(HVAC_MODE_SETS.keys())),
        vol.Optional(CONF_HVAC_FAN_MODE_DP): vol.In(dps),
        vol.Optional(CONF_HVAC_FAN_MODE_SET): vol.In(list(HVAC_FAN_MODE_SETS.keys())),
        vol.Optional(CONF_HVAC_SWING_MODE_DP): vol.In(dps),
        vol.Optional(CONF_HVAC_SWING_MODE_SET): vol.In(
            list(HVAC_SWING_MODE_SETS.keys())
        ),
        vol.Optional(CONF_HVAC_ACTION_DP): vol.In(dps),
        vol.Optional(CONF_HVAC_ACTION_SET): vol.In(list(HVAC_ACTION_SETS.keys())),
        vol.Optional(CONF_ECO_DP): vol.In(dps),
        vol.Optional(CONF_ECO_VALUE): str,
        vol.Optional(CONF_PRESET_DP): vol.In(dps),
        vol.Optional(CONF_PRESET_SET): vol.In(list(PRESET_SETS.keys())),
        vol.Optional(CONF_TEMPERATURE_UNIT): vol.In(
            [TEMPERATURE_CELSIUS, TEMPERATURE_FAHRENHEIT]
        ),
        vol.Optional(CONF_TARGET_PRECISION, default=PRECISION_WHOLE): vol.In(
            [PRECISION_WHOLE, PRECISION_HALVES, PRECISION_TENTHS]
        ),
        vol.Optional(CONF_HEURISTIC_ACTION): bool,
    }


class LocaltuyaClimate(LocalTuyaEntity, ClimateEntity):
    """Tuya climate device."""

    def __init__(
        self,
        device,
        config_entry,
        switchid,
        **kwargs,
    ):
        """Initialize a new LocaltuyaClimate."""
        super().__init__(device, config_entry, switchid, _LOGGER, **kwargs)
        self._state = None
        self._target_temperature = None
        self._current_temperature = None
        self._hvac_mode = None
        self._fan_mode = None
        self._swing_mode = None
        self._preset_mode = None
        self._hvac_action = None
        self._precision = self._config.get(CONF_PRECISION, DEFAULT_PRECISION)
        self._target_precision = self._config.get(
            CONF_TARGET_PRECISION, self._precision
        )
        self._conf_hvac_mode_dp = self._config.get(CONF_HVAC_MODE_DP)
        self._conf_hvac_mode_set = HVAC_MODE_SETS.get(
            self._config.get(CONF_HVAC_MODE_SET), {}
        )
        self._conf_hvac_fan_mode_dp = self._config.get(CONF_HVAC_FAN_MODE_DP)
        self._conf_hvac_fan_mode_set = HVAC_FAN_MODE_SETS.get(
            self._config.get(CONF_HVAC_FAN_MODE_SET), {}
        )
        self._conf_hvac_swing_mode_dp = self._config.get(CONF_HVAC_SWING_MODE_DP)
        self._conf_hvac_swing_mode_set = HVAC_SWING_MODE_SETS.get(
            self._config.get(CONF_HVAC_SWING_MODE_SET), {}
        )
        self._conf_preset_dp = self._config.get(CONF_PRESET_DP)
        self._conf_preset_set = PRESET_SETS.get(self._config.get(CONF_PRESET_SET), {})
        self._conf_hvac_action_dp = self._config.get(CONF_HVAC_ACTION_DP)
        self._conf_hvac_action_set = HVAC_ACTION_SETS.get(
            self._config.get(CONF_HVAC_ACTION_SET), {}
        )
        self._conf_eco_dp = self._config.get(CONF_ECO_DP)
        self._conf_eco_value = self._config.get(CONF_ECO_VALUE, "ECO")
        self._has_presets = self.has_config(CONF_ECO_DP) or self.has_config(
            CONF_PRESET_DP
        )
        _LOGGER.debug("Initialized climate [%s]", self.name)

    @property
    def supported_features(self):
        """Return supported Home Assistant climate features."""
        features = (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        if self.has_config(CONF_TARGET_TEMPERATURE_DP):
            features |= ClimateEntityFeature.TARGET_TEMPERATURE

        if self.has_config(CONF_PRESET_DP) or self.has_config(CONF_ECO_DP):
            features |= ClimateEntityFeature.PRESET_MODE

        if (
            self.has_config(CONF_HVAC_FAN_MODE_DP)
            and self.has_config(CONF_HVAC_FAN_MODE_SET)
        ):
            features |= ClimateEntityFeature.FAN_MODE

        if (
            self.has_config(CONF_HVAC_SWING_MODE_DP)
            and self.has_config(CONF_HVAC_SWING_MODE_SET)
        ):
            features |= ClimateEntityFeature.SWING_MODE

        return features

    @property
    def precision(self):
        """Return the precision of the system."""
        return self._precision

    @property
    def target_precision(self):
        """Return the precision of the target."""
        return self._target_precision

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        if (
            self._config.get(CONF_TEMPERATURE_UNIT, DEFAULT_TEMPERATURE_UNIT)
            == TEMPERATURE_FAHRENHEIT
        ):
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        if not self.has_config(CONF_HVAC_MODE_DP):
            return None
        return list(self._conf_hvac_mode_set) + [HVACMode.OFF]

    @property
    def hvac_action(self):
        """Return the current HVAC action."""
        if not self._config.get(CONF_HEURISTIC_ACTION, False):
            return self._hvac_action

        if self._hvac_mode == HVACMode.OFF or self._state is False:
            self._hvac_action = HVACAction.OFF
            return self._hvac_action

        if (
            self._current_temperature is None
            or self._target_temperature is None
        ):
            return self._hvac_action

        current = self._current_temperature
        target = self._target_temperature
        deadband = max(float(self._precision), 0.0)

        if self._hvac_mode == HVACMode.HEAT:
            if current < target - deadband:
                self._hvac_action = HVACAction.HEATING
            elif current >= target:
                self._hvac_action = HVACAction.IDLE

        elif self._hvac_mode == HVACMode.COOL:
            if current > target + deadband:
                self._hvac_action = HVACAction.COOLING
            elif current <= target:
                self._hvac_action = HVACAction.IDLE

        return self._hvac_action

    @property
    def preset_mode(self):
        """Return current preset."""
        return self._preset_mode

    @property
    def preset_modes(self):
        """Return the list of available presets modes."""
        if not self._has_presets:
            return None
        presets = list(self._conf_preset_set)
        if self._conf_eco_dp and PRESET_ECO not in presets:
            presets.append(PRESET_ECO)
        return presets

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._config.get(CONF_TEMPERATURE_STEP, DEFAULT_TEMPERATURE_STEP)

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        if not self.has_config(CONF_HVAC_FAN_MODE_DP):
            return None
        return list(self._conf_hvac_fan_mode_set)

    @property
    def swing_mode(self):
        """Return the swing setting."""
        return self._swing_mode

    @property
    def swing_modes(self):
        """Return the list of available swing modes."""
        if not self.has_config(CONF_HVAC_SWING_MODE_DP):
            return None
        return list(self._conf_hvac_swing_mode_set)

    async def async_set_temperature(self, **kwargs):
        """Set a new target temperature."""
        if (
            ATTR_TEMPERATURE not in kwargs
            or not self.has_config(CONF_TARGET_TEMPERATURE_DP)
        ):
            return

        requested = kwargs[ATTR_TEMPERATURE]

        if requested is None:
            return

        temperature = round(
            float(requested) / self._target_precision
        )

        await self._device.set_dp(
            temperature,
            self._config[CONF_TARGET_TEMPERATURE_DP],
        )

    async def async_set_fan_mode(self, fan_mode):
        """Set a new fan mode."""
        if self._conf_hvac_fan_mode_dp is None:
            self.warning("Fan mode unsupported: no configured DP")
            return

        if fan_mode not in self._conf_hvac_fan_mode_set:
            self.warning("Unsupported fan mode %r", fan_mode)
            return

        await self._device.set_dp(
            self._conf_hvac_fan_mode_set[fan_mode],
            self._conf_hvac_fan_mode_dp,
        )

    async def async_set_hvac_mode(self, hvac_mode):
        """Set a new HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self._device.set_dp(False, self._dp_id)
            return

        if self._conf_hvac_mode_dp is None:
            self.warning(
                "HVAC mode %r requested but no HVAC mode DP is configured",
                hvac_mode,
            )
            return

        if hvac_mode not in self._conf_hvac_mode_set:
            self.warning("Unsupported HVAC mode %r", hvac_mode)
            return

        if not self._state and self._conf_hvac_mode_dp != self._dp_id:
            await self._device.set_dp(True, self._dp_id)

            # Some thermostats need a small pause after power-on.
            await asyncio.sleep(MODE_WAIT)

        await self._device.set_dp(
            self._conf_hvac_mode_set[hvac_mode],
            self._conf_hvac_mode_dp,
        )

    async def async_set_swing_mode(self, swing_mode):
        """Set a new swing mode."""
        if self._conf_hvac_swing_mode_dp is None:
            self.warning("Swing mode unsupported: no configured DP")
            return

        if swing_mode not in self._conf_hvac_swing_mode_set:
            self.warning("Unsupported swing mode %r", swing_mode)
            return

        await self._device.set_dp(
            self._conf_hvac_swing_mode_set[swing_mode],
            self._conf_hvac_swing_mode_dp,
        )

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self._device.set_dp(True, self._dp_id)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self._device.set_dp(False, self._dp_id)

    async def async_set_preset_mode(self, preset_mode):
        """Set a new preset mode."""
        if preset_mode == PRESET_ECO:
            if self._conf_eco_dp is None:
                self.warning("ECO preset requested without an ECO DP")
                return

            await self._device.set_dp(
                self._conf_eco_value,
                self._conf_eco_dp,
            )
            return

        if (
            self._conf_preset_dp is None
            or preset_mode not in self._conf_preset_set
        ):
            self.warning("Unsupported preset mode %r", preset_mode)
            return

        await self._device.set_dp(
            self._conf_preset_set[preset_mode],
            self._conf_preset_dp,
        )

    @property
    def min_temp(self):
        """Return the minimum target temperature."""
        if self.has_config(CONF_MIN_TEMP_DP):
            value = self.dps_conf(CONF_MIN_TEMP_DP)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value

        return self._config.get(CONF_TEMP_MIN, DEFAULT_MIN_TEMP)

    @property
    def max_temp(self):
        """Return the maximum target temperature."""
        if self.has_config(CONF_MAX_TEMP_DP):
            value = self.dps_conf(CONF_MAX_TEMP_DP)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value

        return self._config.get(CONF_TEMP_MAX, DEFAULT_MAX_TEMP)

    def status_updated(self):
        """Update climate state from Tuya datapoints."""
        super().status_updated()

        if self.has_config(CONF_TARGET_TEMPERATURE_DP):
            value = self.dps_conf(CONF_TARGET_TEMPERATURE_DP)

            if isinstance(value, (int, float)) and not isinstance(value, bool):
                self._target_temperature = (
                    value * self._target_precision
                )
            else:
                self._target_temperature = None

        if self.has_config(CONF_CURRENT_TEMPERATURE_DP):
            value = self.dps_conf(CONF_CURRENT_TEMPERATURE_DP)

            if isinstance(value, (int, float)) and not isinstance(value, bool):
                self._current_temperature = (
                    value * self._precision
                )
            else:
                self._current_temperature = None

        # Presets.
        if self._has_presets:
            self._preset_mode = PRESET_NONE

            if (
                self._conf_eco_dp is not None
                and self.dps(self._conf_eco_dp) == self._conf_eco_value
            ):
                self._preset_mode = PRESET_ECO

            elif (
                self._conf_preset_dp is not None
                and self._conf_preset_set
            ):
                raw_preset = self.dps(self._conf_preset_dp)

                for preset, value in self._conf_preset_set.items():
                    if raw_preset == value:
                        self._preset_mode = preset
                        break

        # HVAC mode.
        if self._conf_hvac_mode_dp is not None:
            if not self._state:
                self._hvac_mode = HVACMode.OFF
            else:
                raw_mode = self.dps(self._conf_hvac_mode_dp)

                for mode, value in self._conf_hvac_mode_set.items():
                    if raw_mode == value:
                        self._hvac_mode = mode
                        break
                else:
                    # Preserve compatibility with devices where HVAC mode
                    # and preset share the same datapoint.
                    self._hvac_mode = HVACMode.AUTO

        # Fan mode.
        if self._conf_hvac_fan_mode_dp is not None:
            raw_fan = self.dps(self._conf_hvac_fan_mode_dp)

            for mode, value in self._conf_hvac_fan_mode_set.items():
                if raw_fan == value:
                    self._fan_mode = mode
                    break
            else:
                self.debug("Unknown fan mode %r", raw_fan)
                self._fan_mode = FAN_AUTO

        # Swing mode.
        if self._conf_hvac_swing_mode_dp is not None:
            raw_swing = self.dps(self._conf_hvac_swing_mode_dp)

            for mode, value in self._conf_hvac_swing_mode_set.items():
                if raw_swing == value:
                    self._swing_mode = mode
                    break
            else:
                self.debug("Unknown swing mode %r", raw_swing)
                self._swing_mode = SWING_OFF

        # Direct HVAC action datapoint.
        if not self._state:
            self._hvac_action = HVACAction.OFF

        elif (
            self._conf_hvac_action_dp is not None
            and self._conf_hvac_action_set
        ):
            raw_action = self.dps(self._conf_hvac_action_dp)

            for action, value in self._conf_hvac_action_set.items():
                if raw_action == value:
                    self._hvac_action = action
                    break


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaClimate, flow_schema)
