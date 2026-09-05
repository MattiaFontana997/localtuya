"""Platform to locally control Tuya water heaters."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    DOMAIN,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_WATER_HEATER_AWAY_DP,
    CONF_WATER_HEATER_AWAY_MODE,
    CONF_WATER_HEATER_AWAY_OFF,
    CONF_WATER_HEATER_AWAY_ON,
    CONF_WATER_HEATER_CURRENT_TEMPERATURE_DP,
    CONF_WATER_HEATER_DEFAULT_MODE,
    CONF_WATER_HEATER_MAX_TEMPERATURE_DP,
    CONF_WATER_HEATER_MIN_TEMPERATURE_DP,
    CONF_WATER_HEATER_MODE_DP,
    CONF_WATER_HEATER_MODE_VALUES,
    CONF_WATER_HEATER_POWER_DP,
    CONF_WATER_HEATER_POWER_OFF,
    CONF_WATER_HEATER_POWER_ON,
    CONF_WATER_HEATER_TARGET_TEMPERATURE_DP,
    CONF_WATER_HEATER_TEMPERATURE_MAX,
    CONF_WATER_HEATER_TEMPERATURE_MIN,
    CONF_WATER_HEATER_TEMPERATURE_SCALING,
    CONF_WATER_HEATER_TEMPERATURE_STEP,
    CONF_WATER_HEATER_TEMPERATURE_UNIT,
    CONF_WATER_HEATER_TEMPERATURE_UNIT_DP,
    CONF_WATER_HEATER_TEMPERATURE_UNIT_VALUES,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_WATER_HEATER_POWER_DP): vol.In(dps),
        vol.Optional(CONF_WATER_HEATER_CURRENT_TEMPERATURE_DP): vol.In(dps),
        vol.Optional(CONF_WATER_HEATER_TARGET_TEMPERATURE_DP): vol.In(dps),
        vol.Optional(CONF_WATER_HEATER_MIN_TEMPERATURE_DP): vol.In(dps),
        vol.Optional(CONF_WATER_HEATER_MAX_TEMPERATURE_DP): vol.In(dps),
        vol.Optional(CONF_WATER_HEATER_TEMPERATURE_UNIT_DP): vol.In(dps),
        vol.Optional(CONF_WATER_HEATER_MODE_DP): vol.In(dps),
        vol.Optional(CONF_WATER_HEATER_AWAY_DP): vol.In(dps),
    }


def _decode(values, raw):
    if isinstance(values, dict):
        for friendly, configured_raw in values.items():
            if raw == configured_raw:
                return friendly
    return None


def _scaled(value, scaling):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(float(value) * scaling, 10)


def _unscaled(value, scaling):
    raw = round(float(value) / scaling, 10)
    return int(raw) if float(raw).is_integer() else raw


def _temperature_unit(value):
    try:
        return UnitOfTemperature(value)
    except (TypeError, ValueError):
        return None


class LocaltuyaWaterHeater(LocalTuyaEntity, WaterHeaterEntity):
    """Representation of a Tuya water heater."""

    def __init__(self, device, config_entry, heaterid, **kwargs):
        """Initialize the Tuya water heater."""
        super().__init__(device, config_entry, heaterid, _LOGGER, **kwargs)
        self._scaling = float(self._config.get(CONF_WATER_HEATER_TEMPERATURE_SCALING, 1.0))
        if self._scaling <= 0:
            raise ValueError("Water heater temperature scaling must be greater than zero")

        self._temp_min = float(self._config.get(CONF_WATER_HEATER_TEMPERATURE_MIN, 5.0))
        self._temp_max = float(self._config.get(CONF_WATER_HEATER_TEMPERATURE_MAX, 90.0))
        self._temp_step = float(self._config.get(CONF_WATER_HEATER_TEMPERATURE_STEP, 1.0))
        if self._temp_max < self._temp_min or self._temp_step <= 0:
            raise ValueError("Invalid water heater temperature range")

        self._power_on = self._config.get(CONF_WATER_HEATER_POWER_ON, True)
        self._power_off = self._config.get(CONF_WATER_HEATER_POWER_OFF, False)
        self._mode_values = self._config.get(CONF_WATER_HEATER_MODE_VALUES, {})
        self._unit_values = self._config.get(CONF_WATER_HEATER_TEMPERATURE_UNIT_VALUES, {})
        self._away_on = self._config.get(CONF_WATER_HEATER_AWAY_ON, True)
        self._away_off = self._config.get(CONF_WATER_HEATER_AWAY_OFF, False)
        self._away_mode = str(self._config.get(CONF_WATER_HEATER_AWAY_MODE, "away"))
        self._default_mode = self._config.get(CONF_WATER_HEATER_DEFAULT_MODE)

        features = WaterHeaterEntityFeature(0)
        if self.has_config(CONF_WATER_HEATER_POWER_DP):
            features |= WaterHeaterEntityFeature.ON_OFF
        if self.has_config(CONF_WATER_HEATER_TARGET_TEMPERATURE_DP):
            features |= WaterHeaterEntityFeature.TARGET_TEMPERATURE
        if self.has_config(CONF_WATER_HEATER_MODE_DP) and self._mode_values:
            features |= WaterHeaterEntityFeature.OPERATION_MODE
        if self.has_config(CONF_WATER_HEATER_AWAY_DP) or self._away_mode in self._mode_values:
            features |= WaterHeaterEntityFeature.AWAY_MODE
        self._attr_supported_features = features

    @property
    def temperature_unit(self):
        """Return the temperature unit."""
        unit_dp = self._config.get(CONF_WATER_HEATER_TEMPERATURE_UNIT_DP)
        if unit_dp is not None:
            friendly = _decode(self._unit_values, self.dps(unit_dp))
            if unit := _temperature_unit(friendly):
                return unit
        configured = self._config.get(
            CONF_WATER_HEATER_TEMPERATURE_UNIT,
            UnitOfTemperature.CELSIUS,
        )
        return _temperature_unit(configured) or UnitOfTemperature.CELSIUS

    @property
    def precision(self):
        """Return temperature display precision."""
        return self._temp_step if self._temp_step <= 1.0 else 1.0

    @property
    def current_temperature(self):
        """Return current water temperature."""
        dp_id = self._config.get(CONF_WATER_HEATER_CURRENT_TEMPERATURE_DP)
        return _scaled(self.dps(dp_id), self._scaling) if dp_id is not None else None

    @property
    def target_temperature(self):
        """Return target water temperature."""
        dp_id = self._config.get(CONF_WATER_HEATER_TARGET_TEMPERATURE_DP)
        return _scaled(self.dps(dp_id), self._scaling) if dp_id is not None else None

    @property
    def target_temperature_step(self):
        """Return target temperature step."""
        return self._temp_step

    @property
    def min_temp(self):
        """Return minimum target temperature."""
        dp_id = self._config.get(CONF_WATER_HEATER_MIN_TEMPERATURE_DP)
        value = _scaled(self.dps(dp_id), self._scaling) if dp_id is not None else None
        return value if value is not None else self._temp_min

    @property
    def max_temp(self):
        """Return maximum target temperature."""
        dp_id = self._config.get(CONF_WATER_HEATER_MAX_TEMPERATURE_DP)
        value = _scaled(self.dps(dp_id), self._scaling) if dp_id is not None else None
        return value if value is not None else self._temp_max

    @property
    def current_operation(self):
        """Return current operation mode."""
        dp_id = self._config.get(CONF_WATER_HEATER_MODE_DP)
        if dp_id is not None:
            mode = _decode(self._mode_values, self.dps(dp_id))
            return "eco" if mode == self._away_mode else mode

        power_dp = self._config.get(CONF_WATER_HEATER_POWER_DP)
        if power_dp is not None:
            raw = self.dps(power_dp)
            if raw == self._power_on:
                return "on"
            if raw == self._power_off:
                return "off"
        return None

    @property
    def operation_list(self):
        """Return available operation modes."""
        if not self._mode_values:
            return None
        return [mode for mode in self._mode_values if mode != self._away_mode]

    @property
    def is_away_mode_on(self):
        """Return whether away mode is active."""
        away_dp = self._config.get(CONF_WATER_HEATER_AWAY_DP)
        if away_dp is not None:
            raw = self.dps(away_dp)
            if raw == self._away_on:
                return True
            if raw == self._away_off:
                return False
            return None
        mode_dp = self._config.get(CONF_WATER_HEATER_MODE_DP)
        if mode_dp is not None:
            return _decode(self._mode_values, self.dps(mode_dp)) == self._away_mode
        return None

    async def async_set_temperature(self, **kwargs):
        """Set target temperature and optional operation mode."""
        if kwargs.get(ATTR_OPERATION_MODE) is not None:
            await self.async_set_operation_mode(kwargs[ATTR_OPERATION_MODE])
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            dp_id = self._config.get(CONF_WATER_HEATER_TARGET_TEMPERATURE_DP)
            if dp_id is None:
                raise NotImplementedError()
            await self._device.set_dp(
                _unscaled(kwargs[ATTR_TEMPERATURE], self._scaling),
                dp_id,
            )

    async def async_set_operation_mode(self, operation_mode):
        """Set the exact catalog-provided raw operation mode."""
        dp_id = self._config.get(CONF_WATER_HEATER_MODE_DP)
        if dp_id is None or operation_mode not in self._mode_values:
            raise NotImplementedError()
        await self._device.set_dp(self._mode_values[operation_mode], dp_id)

    async def async_turn_away_mode_on(self):
        """Enable away mode."""
        away_dp = self._config.get(CONF_WATER_HEATER_AWAY_DP)
        if away_dp is not None:
            await self._device.set_dp(self._away_on, away_dp)
            return
        if self._away_mode in self._mode_values:
            await self.async_set_operation_mode(self._away_mode)
            return
        raise NotImplementedError()

    async def async_turn_away_mode_off(self):
        """Disable away mode."""
        away_dp = self._config.get(CONF_WATER_HEATER_AWAY_DP)
        if away_dp is not None:
            await self._device.set_dp(self._away_off, away_dp)
            return
        candidates = [mode for mode in self._mode_values if mode != self._away_mode]
        mode = self._default_mode if self._default_mode in candidates else (candidates[0] if candidates else None)
        if mode is None:
            raise NotImplementedError()
        await self.async_set_operation_mode(mode)

    async def async_turn_on(self, **kwargs):
        """Turn on the water heater."""
        dp_id = self._config.get(CONF_WATER_HEATER_POWER_DP)
        if dp_id is None:
            raise NotImplementedError()
        await self._device.set_dp(self._power_on, dp_id)

    async def async_turn_off(self, **kwargs):
        """Turn off the water heater."""
        dp_id = self._config.get(CONF_WATER_HEATER_POWER_DP)
        if dp_id is None:
            raise NotImplementedError()
        await self._device.set_dp(self._power_off, dp_id)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaWaterHeater, flow_schema)
