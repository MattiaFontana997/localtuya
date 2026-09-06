"""Platform to present any Tuya DP as an enumeration."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.select import DOMAIN, SelectEntity

from .common import LocalTuyaEntity, async_setup_entry
from .const import CONF_DEFAULT_VALUE, CONF_OPTIONS, CONF_OPTIONS_FRIENDLY, CONF_PASSIVE_ENTITY, CONF_RESTORE_ON_RECONNECT

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    return {
        vol.Required(CONF_OPTIONS): vol.All(str, vol.Length(min=1)),
        vol.Optional(CONF_OPTIONS_FRIENDLY): str,
        vol.Required(CONF_RESTORE_ON_RECONNECT): bool,
        vol.Required(CONF_PASSIVE_ENTITY): bool,
        vol.Optional(CONF_DEFAULT_VALUE): str,
    }


class LocaltuyaSelect(LocalTuyaEntity, SelectEntity):
    def __init__(self, device, config_entry, sensorid, **kwargs):
        super().__init__(device, config_entry, sensorid, _LOGGER, **kwargs)
        self._state = None
        self._current_option = None
        self._valid_options = [option.strip() for option in self._config[CONF_OPTIONS].split(";") if option.strip()]
        if not self._valid_options:
            raise ValueError("Select requires at least one non-empty option")
        friendly = self._config.get(CONF_OPTIONS_FRIENDLY, "")
        display_options = [option.strip() for option in friendly.split(";") if option.strip()]
        if not display_options:
            display_options = self._valid_options.copy()
        if len(display_options) < len(self._valid_options):
            display_options.extend(self._valid_options[len(display_options):])
        elif len(display_options) > len(self._valid_options):
            display_options = display_options[:len(self._valid_options)]
        if len(set(display_options)) != len(display_options):
            display_options = self._valid_options.copy()
        self._display_options = display_options

    @property
    def current_option(self) -> str | None:
        return self._current_option

    @property
    def options(self) -> list[str]:
        return self._display_options

    async def async_select_option(self, option: str) -> None:
        try:
            index = self._display_options.index(option)
        except ValueError:
            self.warning("Unknown select option %r for entity %s", option, self.entity_id)
            return
        await self.set_mapped_dp(self._valid_options[index])

    def status_updated(self):
        state = self.dps(self._dp_id)
        self._state = state
        if state is None:
            self._current_option = None
            return
        text = str(state)
        if text in self._valid_options:
            self._current_option = self._display_options[self._valid_options.index(text)]
        elif text in self._display_options:
            self._current_option = text
        else:
            self._current_option = None
            self.warning("Select entity %s received unknown mapped option %r", self.entity_id, state)
            return
        if not self._device.is_connecting:
            self._last_state = state

    def entity_default_value(self):
        return self._valid_options[0]


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaSelect, flow_schema)
