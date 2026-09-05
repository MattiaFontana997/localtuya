"""Platform to locally control Tuya alarm control panels."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.alarm_control_panel import DOMAIN, AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelEntityFeature as Feature, AlarmControlPanelState

from .common import LocalTuyaEntity, async_setup_entry
from .const import CONF_ALARM_STATE_DP, CONF_ALARM_STATE_VALUES, CONF_ALARM_TRIGGER_DP, CONF_ALARM_TRIGGER_ON

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    return {
        vol.Optional(CONF_ALARM_STATE_DP): vol.In(dps),
        vol.Optional(CONF_ALARM_TRIGGER_DP): vol.In(dps),
    }


def _decode(values, raw):
    for friendly, configured_raw in (values or {}).items():
        if raw == configured_raw:
            return friendly
    return None


class LocaltuyaAlarmControlPanel(LocalTuyaEntity, AlarmControlPanelEntity):
    def __init__(self, device, config_entry, dp_id, **kwargs):
        super().__init__(device, config_entry, dp_id, _LOGGER, **kwargs)
        self._state_values = self._config.get(CONF_ALARM_STATE_VALUES, {})
        support = Feature(0)
        states = set(self._state_values)
        if AlarmControlPanelState.ARMED_HOME in states or AlarmControlPanelState.ARMED_HOME.value in states:
            support |= Feature.ARM_HOME
        if AlarmControlPanelState.ARMED_AWAY in states or AlarmControlPanelState.ARMED_AWAY.value in states:
            support |= Feature.ARM_AWAY
        if AlarmControlPanelState.ARMED_NIGHT in states or AlarmControlPanelState.ARMED_NIGHT.value in states:
            support |= Feature.ARM_NIGHT
        if AlarmControlPanelState.ARMED_VACATION in states or AlarmControlPanelState.ARMED_VACATION.value in states:
            support |= Feature.ARM_VACATION
        if AlarmControlPanelState.ARMED_CUSTOM_BYPASS in states or AlarmControlPanelState.ARMED_CUSTOM_BYPASS.value in states:
            support |= Feature.ARM_CUSTOM_BYPASS
        if self.has_config(CONF_ALARM_TRIGGER_DP) or AlarmControlPanelState.TRIGGERED.value in states:
            support |= Feature.TRIGGER
        self._attr_supported_features = support
        self._attr_code_format = None
        self._attr_code_arm_required = False

    @property
    def alarm_state(self):
        if self.has_config(CONF_ALARM_TRIGGER_DP):
            if self.dps(self._config[CONF_ALARM_TRIGGER_DP]) == self._config.get(CONF_ALARM_TRIGGER_ON, True):
                return AlarmControlPanelState.TRIGGERED
        dp_id = self._config.get(CONF_ALARM_STATE_DP, self._dp_id)
        friendly = _decode(self._state_values, self.dps(dp_id))
        if friendly is None:
            return None
        try:
            return AlarmControlPanelState(friendly)
        except ValueError:
            return None

    async def _send(self, state):
        friendly = state.value if hasattr(state, "value") else str(state)
        if friendly not in self._state_values:
            raise NotImplementedError()
        await self._device.set_dp(self._state_values[friendly], self._config.get(CONF_ALARM_STATE_DP, self._dp_id))

    async def async_alarm_disarm(self, code=None):
        await self._send(AlarmControlPanelState.DISARMED)

    async def async_alarm_arm_home(self, code=None):
        await self._send(AlarmControlPanelState.ARMED_HOME)

    async def async_alarm_arm_away(self, code=None):
        await self._send(AlarmControlPanelState.ARMED_AWAY)

    async def async_alarm_arm_night(self, code=None):
        await self._send(AlarmControlPanelState.ARMED_NIGHT)

    async def async_alarm_arm_vacation(self, code=None):
        await self._send(AlarmControlPanelState.ARMED_VACATION)

    async def async_alarm_arm_custom_bypass(self, code=None):
        await self._send(AlarmControlPanelState.ARMED_CUSTOM_BYPASS)

    async def async_alarm_trigger(self, code=None):
        if self.has_config(CONF_ALARM_TRIGGER_DP):
            await self._device.set_dp(self._config.get(CONF_ALARM_TRIGGER_ON, True), self._config[CONF_ALARM_TRIGGER_DP])
            return
        await self._send(AlarmControlPanelState.TRIGGERED)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaAlarmControlPanel, flow_schema)
