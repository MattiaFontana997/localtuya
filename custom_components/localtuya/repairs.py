"""Home Assistant repair flows for LocalTuya."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_DEVICES, CONF_HOST
from homeassistant.core import HomeAssistant

from .config_flow import CannotConnect, EmptyDpsList, InvalidAuth, validate_input
from .const import CONF_PRODUCT_KEY, DATA_DISCOVERY, DOMAIN
from .host_recovery import HostRecoveryOutcome, async_recover_discovered_host
from .repair_issues import async_clear_host_recovery_issue, host_recovery_issue_id

_DISCOVERY_SETTLE_SECONDS = 2.0
_RECOVERY_SUCCESS = {
    HostRecoveryOutcome.UNCHANGED,
    HostRecoveryOutcome.UPDATED,
    HostRecoveryOutcome.METADATA_UPDATED,
}


@dataclass(slots=True)
class _RepairTarget:
    """In-memory target for one privacy-safe repair issue."""

    entry: ConfigEntry
    device_id: str
    device_data: dict[str, Any]

    @property
    def device_name(self) -> str:
        """Return a friendly label without exposing the Tuya device ID."""
        name = self.device_data.get("friendly_name")
        return str(name or "LocalTuya device").strip() or "LocalTuya device"


def _find_repair_target(hass: HomeAssistant, issue_id: str) -> _RepairTarget | None:
    """Resolve a hashed repair issue back to its configured device in memory."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        devices = entry.data.get(CONF_DEVICES, {})
        if not isinstance(devices, dict):
            continue

        for device_id, device_data in devices.items():
            if not isinstance(device_data, dict):
                continue
            if host_recovery_issue_id(device_id) != issue_id:
                continue
            return _RepairTarget(entry, device_id, device_data)

    return None


def _validation_error_key(error_type: str | None) -> str:
    """Map a private validation exception class to a stable UI error key."""
    return {
        CannotConnect.__name__: "cannot_connect",
        InvalidAuth.__name__: "invalid_auth",
        EmptyDpsList.__name__: "empty_dps",
    }.get(str(error_type), "unknown")


class HostRecoveryRepairFlow(RepairsFlow):
    """Repair a LocalTuya device whose discovered host could not be validated."""

    def __init__(self, target: _RepairTarget) -> None:
        """Initialize the repair flow."""
        self._target = target
        super().__init__()

    def _placeholders(self) -> dict[str, str]:
        """Return privacy-safe translation placeholders."""
        return {"device_name": self._target.device_name}

    def _current_device_data(self) -> dict[str, Any] | None:
        """Return fresh config-entry data instead of the flow's initial snapshot."""
        devices = self._target.entry.data.get(CONF_DEVICES, {})
        if not isinstance(devices, dict):
            return None

        current = devices.get(self._target.device_id)
        return current if isinstance(current, dict) else None

    def _manual_host_form(
        self,
        *,
        user_input: dict[str, str] | None = None,
        errors: dict[str, str] | None = None,
        suggested_host: str | None = None,
    ) -> RepairsFlowResult:
        """Return the validated manual-address form."""
        values = dict(user_input or {})
        if suggested_host and CONF_HOST not in values:
            values[CONF_HOST] = suggested_host

        schema = vol.Schema({vol.Required(CONF_HOST): str})
        return self.async_show_form(
            step_id="manual_host",
            data_schema=self.add_suggested_values_to_schema(schema, values),
            errors=errors or {},
            description_placeholders=self._placeholders(),
        )

    async def async_step_init(
        self,
        user_input: dict[str, str] | None = None,
    ) -> RepairsFlowResult:
        """Offer automatic rediscovery or a validated manual address."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["rediscover", "manual_host"],
            description_placeholders=self._placeholders(),
        )

    async def _async_validate_current_host(self) -> str | None:
        """Validate the currently configured host and clear the issue on success."""
        current = self._current_device_data()
        if current is None:
            return "device_not_found"

        probe_data = copy.deepcopy(current)
        probe_data[CONF_DEVICE_ID] = self._target.device_id

        try:
            await validate_input(self.hass, probe_data)
        except CannotConnect:
            return "cannot_connect"
        except InvalidAuth:
            return "invalid_auth"
        except EmptyDpsList:
            return "empty_dps"
        except Exception:  # noqa: BLE001 - repair UI must fail closed.
            return "unknown"

        async_clear_host_recovery_issue(self.hass, self._target.device_id)
        return None

    async def _async_apply_candidate(
        self,
        candidate_host: str,
        *,
        product_key: str | None = None,
    ) -> str | None:
        """Validate a candidate host and persist it only when it is genuine."""
        candidate_host = str(candidate_host or "").strip()
        if not candidate_host:
            return "invalid_host"

        current = self._current_device_data()
        if current is None:
            return "device_not_found"

        configured_host = str(current.get(CONF_HOST, "")).strip()

        if candidate_host == configured_host:
            return await self._async_validate_current_host()

        result = await async_recover_discovered_host(
            self.hass,
            self._target.entry,
            self._target.device_id,
            candidate_host,
            validator=validate_input,
            product_key=product_key,
        )

        if result.outcome in _RECOVERY_SUCCESS:
            async_clear_host_recovery_issue(self.hass, self._target.device_id)
            return None

        if result.outcome is HostRecoveryOutcome.VALIDATION_FAILED:
            return _validation_error_key(result.validation_error_type)

        if result.outcome is HostRecoveryOutcome.STALE:
            return "stale"

        if result.outcome is HostRecoveryOutcome.INVALID_ADDRESS:
            return "invalid_host"

        return "device_not_found"

    async def async_step_rediscover(
        self,
        user_input: dict[str, str] | None = None,
    ) -> RepairsFlowResult:
        """Actively rediscover the device and validate the discovered address."""
        discovery = self.hass.data.get(DOMAIN, {}).get(DATA_DISCOVERY)
        if discovery is None:
            return self._manual_host_form(errors={"base": "discovery_unavailable"})

        request_discovery = getattr(discovery, "async_request_discovery", None)
        if not callable(request_discovery):
            return self._manual_host_form(errors={"base": "discovery_unavailable"})

        try:
            await request_discovery()
            await asyncio.sleep(_DISCOVERY_SETTLE_SECONDS)
        except Exception:  # noqa: BLE001 - network discovery is recoverable.
            return self._manual_host_form(errors={"base": "discovery_failed"})

        devices = getattr(discovery, "devices", {})
        candidate = devices.get(self._target.device_id) if isinstance(devices, dict) else None
        if not isinstance(candidate, dict):
            return self._manual_host_form(errors={"base": "device_not_found"})

        host = candidate.get("ip")
        if not host:
            return self._manual_host_form(errors={"base": "device_not_found"})

        error = await self._async_apply_candidate(
            str(host),
            product_key=(
                candidate.get("productKey")
                or candidate.get(CONF_PRODUCT_KEY)
            ),
        )
        if error is not None:
            return self._manual_host_form(
                errors={"base": error},
                suggested_host=str(host),
            )

        return self.async_create_entry(title="", data={})

    async def async_step_manual_host(
        self,
        user_input: dict[str, str] | None = None,
    ) -> RepairsFlowResult:
        """Validate and save a user-supplied LAN address."""
        if user_input is not None:
            error = await self._async_apply_candidate(user_input.get(CONF_HOST, ""))
            if error is None:
                return self.async_create_entry(title="", data={})
            return self._manual_host_form(
                user_input=user_input,
                errors={"base": error},
            )

        return self._manual_host_form()


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow for a LocalTuya host recovery issue."""
    if issue_id.startswith("host_recovery_") and (
        target := _find_repair_target(hass, issue_id)
    ) is not None:
        return HostRecoveryRepairFlow(target)

    return ConfirmRepairFlow()
