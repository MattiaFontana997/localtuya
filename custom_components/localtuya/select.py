"""Platform to present any Tuya DP as an enumeration."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.select import DOMAIN, SelectEntity

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_DEFAULT_VALUE,
    CONF_OPTIONS,
    CONF_OPTIONS_FRIENDLY,
    CONF_PASSIVE_ENTITY,
    CONF_RESTORE_ON_RECONNECT,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Required(CONF_OPTIONS): vol.All(str, vol.Length(min=1)),
        vol.Optional(CONF_OPTIONS_FRIENDLY): str,
        vol.Required(CONF_RESTORE_ON_RECONNECT): bool,
        vol.Required(CONF_PASSIVE_ENTITY): bool,
        vol.Optional(CONF_DEFAULT_VALUE): str,
    }


class LocaltuyaSelect(LocalTuyaEntity, SelectEntity):
    """Representation of a Tuya enumeration."""

    def __init__(
        self,
        device,
        config_entry,
        sensorid,
        **kwargs,
    ):
        """Initialize the Tuya select."""
        super().__init__(device, config_entry, sensorid, _LOGGER, **kwargs)

        self._state = None
        self._current_option = None

        self._valid_options = [
            option.strip()
            for option in self._config[CONF_OPTIONS].split(";")
            if option.strip()
        ]

        if not self._valid_options:
            raise ValueError("Select requires at least one non-empty option")

        friendly = self._config.get(CONF_OPTIONS_FRIENDLY, "")
        display_options = [
            option.strip()
            for option in friendly.split(";")
            if option.strip()
        ]

        if not display_options:
            display_options = self._valid_options.copy()

        if len(display_options) < len(self._valid_options):
            display_options.extend(
                self._valid_options[len(display_options):]
            )
        elif len(display_options) > len(self._valid_options):
            self.warning(
                "Ignoring %d extra friendly select options",
                len(display_options) - len(self._valid_options),
            )
            display_options = display_options[: len(self._valid_options)]

        if len(set(display_options)) != len(display_options):
            self.warning(
                "Friendly select options contain duplicates; using raw options"
            )
            display_options = self._valid_options.copy()

        self._display_options = display_options

    @property
    def current_option(self) -> str | None:
        """Return the current display option."""
        return self._current_option

    @property
    def options(self) -> list[str]:
        """Return available display options."""
        return self._display_options

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        try:
            index = self._display_options.index(option)
        except ValueError:
            self.warning(
                "Unknown select option %r for entity %s",
                option,
                self.entity_id,
            )
            return

        await self._device.set_dp(
            self._valid_options[index],
            self._dp_id,
        )

    def status_updated(self):
        """Update the selected option."""
        raw_state = self.dps(self._dp_id)
        self._state = raw_state

        if raw_state is None:
            self._current_option = None
            return

        try:
            index = self._valid_options.index(str(raw_state))
        except ValueError:
            self._current_option = None
            self.warning(
                "Select entity %s received unknown raw option %r",
                self.entity_id,
                raw_state,
            )
            return

        self._current_option = self._display_options[index]

        if not self._device.is_connecting:
            self._last_state = raw_state

    def entity_default_value(self):
        """Return the first raw option as the default value."""
        return self._valid_options[0]


async_setup_entry = partial(
    async_setup_entry,
    DOMAIN,
    LocaltuyaSelect,
    flow_schema,
)
