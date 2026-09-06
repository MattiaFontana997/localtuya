"""Platform to locally control Tuya-based lock devices."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.lock import DOMAIN, LockEntity, LockEntityFeature

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_LOCK_COMMAND_VALUES,
    CONF_LOCK_JAMMED_DP,
    CONF_LOCK_JAMMED_VALUES,
    CONF_LOCK_OPEN_DP,
    CONF_LOCK_OPEN_VALUES,
    CONF_LOCK_OPEN_WRITABLE,
    CONF_LOCK_STATE_DP,
    CONF_LOCK_STATE_VALUES,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_LOCK_STATE_DP): vol.In(dps),
        vol.Optional(CONF_LOCK_OPEN_DP): vol.In(dps),
        vol.Optional(CONF_LOCK_JAMMED_DP): vol.In(dps),
        vol.Optional(CONF_LOCK_OPEN_WRITABLE, default=False): bool,
    }


def _friendly_for_raw(values, raw):
    if not isinstance(values, dict):
        return None
    for friendly, configured_raw in values.items():
        if raw == configured_raw:
            return friendly
    return None


class LocaltuyaLock(LocalTuyaEntity, LockEntity):
    """Representation of a Tuya lock using directly writable lock semantics."""

    def __init__(self, device, config_entry, lockid, **kwargs):
        """Initialize the Tuya lock."""
        super().__init__(device, config_entry, lockid, _LOGGER, **kwargs)

        self._command_values = self._config.get(
            CONF_LOCK_COMMAND_VALUES,
            {"lock": True, "unlock": False},
        )
        self._state_values = self._config.get(
            CONF_LOCK_STATE_VALUES,
            {"locked": True, "unlocked": False},
        )
        self._open_values = self._config.get(
            CONF_LOCK_OPEN_VALUES,
            {"open": True, "closed": False},
        )
        self._jammed_values = self._config.get(
            CONF_LOCK_JAMMED_VALUES,
            {"jammed": True, "clear": False},
        )

        if self._config.get(CONF_LOCK_OPEN_WRITABLE, False) and self.has_config(
            CONF_LOCK_OPEN_DP
        ):
            self._attr_supported_features = LockEntityFeature.OPEN

    @property
    def is_locked(self) -> bool | None:
        """Return whether the lock is locked."""
        dp_id = self._config.get(CONF_LOCK_STATE_DP, self._dp_id)
        raw = self.dps(dp_id)
        friendly = _friendly_for_raw(self._state_values, raw)
        if friendly == "locked":
            return True
        if friendly == "unlocked":
            return False

        # A command DP can double as a state DP. Accept its exact configured
        # write values as a fallback without guessing other raw states.
        if dp_id == self._dp_id:
            if raw == self._command_values.get("lock"):
                return True
            if raw == self._command_values.get("unlock"):
                return False
        return None

    @property
    def is_open(self) -> bool | None:
        """Return whether the latch/door is open when reported."""
        if not self.has_config(CONF_LOCK_OPEN_DP):
            return None
        raw = self.dps(self._config[CONF_LOCK_OPEN_DP])
        friendly = _friendly_for_raw(self._open_values, raw)
        if friendly == "open":
            return True
        if friendly == "closed":
            return False
        return None

    @property
    def is_jammed(self) -> bool | None:
        """Return whether the lock reports a jam."""
        if not self.has_config(CONF_LOCK_JAMMED_DP):
            return None
        raw = self.dps(self._config[CONF_LOCK_JAMMED_DP])
        friendly = _friendly_for_raw(self._jammed_values, raw)
        if friendly == "jammed":
            return True
        if friendly in {"clear", "normal", "not_jammed"}:
            return False
        return None

    async def async_lock(self, **kwargs) -> None:
        """Lock using the exact catalog-provided raw value."""
        if "lock" not in self._command_values:
            raise NotImplementedError()
        await self._device.set_dp(self._command_values["lock"], self._dp_id)

    async def async_unlock(self, **kwargs) -> None:
        """Unlock using the exact catalog-provided raw value."""
        if "unlock" not in self._command_values:
            raise NotImplementedError()
        await self._device.set_dp(self._command_values["unlock"], self._dp_id)

    async def async_open(self, **kwargs) -> None:
        """Open the latch when the catalog marks that DP writable."""
        if not (
            self._config.get(CONF_LOCK_OPEN_WRITABLE, False)
            and self.has_config(CONF_LOCK_OPEN_DP)
        ):
            raise NotImplementedError()
        if "open" not in self._open_values:
            raise NotImplementedError()
        await self._device.set_dp(
            self._open_values["open"],
            self._config[CONF_LOCK_OPEN_DP],
        )


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaLock, flow_schema)
