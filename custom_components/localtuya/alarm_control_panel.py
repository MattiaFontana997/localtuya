"""Platform to locally control Tuya alarm control panels."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.alarm_control_panel import DOMAIN, AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_ALARM_STATE_DP,
    CONF_ALARM_STATE_VALUES,
    CONF_ALARM_TRIGGER_DP,
    CONF_ALARM_TRIGGER_OFF,
    CONF_ALARM_TRIGGER_ON,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_ALARM_STATE_DP): vol.In(dps),
        vol.Optional(CONF_ALARM_TRIGGER_DP): vol.In(dps),
    }


def _friendly_for_raw(values, raw):
    if not isinstance(values, dict):
        return None
    for friendly, configured_raw in values.items():
        if raw == configured_raw:
            return friendly
    return None


class LocaltuyaAlarmControlPanel(LocalTuyaEntity, AlarmControlPanelEntity):
    """Representation of a Tuya alarm control panel."""

    def __init__(self, device, config_entry, alarmid, **kwargs):
        """Initialize the Tuya alarm control panel."""
        super().__init__(device, config_entry, alarmid, _LOGGER, **kwargs)
        self._state_values = self._config.get(CONF_ALARM_STATE_VALUES, {})
        self._trigger_on = self._config.get(CONF_ALARM_TRIGGER_ON, True)
        self._trigger_off = self._config.get(CONF_ALARM_TRIGGER_OFF, False)
        self._attr_code_format = None
        self._attr_code_arm_required = False

        features = AlarmControlPanelEntityFeature(0)
        state_features = {
            AlarmControlPanelState.ARMED_HOME.value: AlarmControlPanelEntityFeature.ARM_HOME,
            AlarmControlPanelState.ARMED_AWAY.value: AlarmControlPanelEntityFeature.ARM_AWAY,
            AlarmControlPanelState.ARMED_NIGHT.value: AlarmControlPanelEntityFeature.ARM_NIGHT,
            AlarmControlPanelState.ARMED_VACATION.value: AlarmControlPanelEntityFeature.ARM_VACATION,
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS.value: AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS,
        }
        for state, feature in state_features.items():
            if state in self._state_values:
                features |= feature
        if self.has_config(CONF_ALARM_TRIGGER_DP) or AlarmControlPanelState.TRIGGERED.value in self._state_values:
            features |= AlarmControlPanelEntityFeature.TRIGGER
        self._attr_supported_features = features

    @property
    def alarm_state(self):
        """Return current alarm state."""
        trigger_dp = self._config.get(CONF_ALARM_TRIGGER_DP)
        if trigger_dp is not None:
            raw_trigger = self.dps(trigger_dp)
            if raw_trigger == self._trigger_on:
                return AlarmControlPanelState.TRIGGERED
            if raw_trigger not in (self._trigger_off, None):
                self.warning("Ignoring unknown alarm trigger value %r", raw_trigger)

        state_dp = self._config.get(CONF_ALARM_STATE_DP, self._dp_id)
        friendly = _friendly_for_raw(self._state_values, self.dps(state_dp))
        if friendly is None:
            return None
        try:
            return AlarmControlPanelState(friendly)
        except ValueError:
            self.warning("Ignoring unsupported alarm state %r", friendly)
            return None

    async def _async_send_state(self, state):
        key = state.value if isinstance(state, AlarmControlPanelState) else str(state)
        if key not in self._state_values:
            raise NotImplementedError()
        state_dp = self._config.get(CONF_ALARM_STATE_DP, self._dp_id)
        await self._device.set_dp(self._state_values[key], state_dp)

    async def async_alarm_disarm(self, code=None):
        """Disarm the alarm."""
        await self._async_send_state(AlarmControlPanelState.DISARMED)

    async def async_alarm_arm_home(self, code=None):
        """Arm home."""
        await self._async_send_state(AlarmControlPanelState.ARMED_HOME)

    async def async_alarm_arm_away(self, code=None):
        """Arm away."""
        await self._async_send_state(AlarmControlPanelState.ARMED_AWAY)

    async def async_alarm_arm_night(self, code=None):
        """Arm night."""
        await self._async_send_state(AlarmControlPanelState.ARMED_NIGHT)

    async def async_alarm_arm_vacation(self, code=None):
        """Arm vacation."""
        await self._async_send_state(AlarmControlPanelState.ARMED_VACATION)

    async def async_alarm_arm_custom_bypass(self, code=None):
        """Arm custom bypass."""
        await self._async_send_state(AlarmControlPanelState.ARMED_CUSTOM_BYPASS)

    async def async_alarm_trigger(self, code=None):
        """Trigger the alarm."""
        trigger_dp = self._config.get(CONF_ALARM_TRIGGER_DP)
        if trigger_dp is not None:
            await self._device.set_dp(self._trigger_on, trigger_dp)
            return
        await self._async_send_state(AlarmControlPanelState.TRIGGERED)


async_setup_entry = partial(
    async_setup_entry,
    DOMAIN,
    LocaltuyaAlarmControlPanel,
    flow_schema,
)
