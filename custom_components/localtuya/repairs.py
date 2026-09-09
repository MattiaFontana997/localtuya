"""Home Assistant repair flows for LocalTuya."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_DEVICES, CONF_HOST
from homeassistant.core import HomeAssistant

from .config_flow import CannotConnect, EmptyDpsList, InvalidAuth, validate_input
from .const import (
    ATTR_UPDATED_AT,
    CONF_DPS_STRINGS,
    CONF_LOCAL_KEY,
    CONF_PRODUCT_KEY,
    CONF_PROTOCOL_VERSION,
    DATA_DISCOVERY,
    DOMAIN,
)
from .device_probe import PROTOCOL_AUTO, SUPPORTED_PROTOCOL_VERSIONS
from .host_recovery import HostRecoveryOutcome, async_recover_discovered_host
from .qr_onboarding import CONF_QR_AUTH, QrCloudClient, QrProvisioningError
from .repair_issues import (
    HEALTH_FAILURE_TRANSLATIONS,
    async_clear_device_health_issues,
    async_clear_host_recovery_issue,
    device_health_issue_id,
    host_recovery_issue_id,
)

_DISCOVERY_SETTLE_SECONDS = 2.0
_RECOVERY_SUCCESS = {
    HostRecoveryOutcome.UNCHANGED,
    HostRecoveryOutcome.UPDATED,
    HostRecoveryOutcome.METADATA_UPDATED,
}


@dataclass(slots=True)
class _RepairTarget:
    """In-memory target for one privacy-safe Repair issue."""

    entry: ConfigEntry
    device_id: str
    device_data: dict[str, Any]
    failure: str

    @property
    def device_name(self) -> str:
        name = self.device_data.get("friendly_name")
        return str(name or "LocalTuya device").strip() or "LocalTuya device"


def _find_repair_target(hass: HomeAssistant, issue_id: str) -> _RepairTarget | None:
    """Resolve a hashed issue ID back to a configured device in memory."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        devices = entry.data.get(CONF_DEVICES, {})
        if not isinstance(devices, dict):
            continue
        for device_id, device_data in devices.items():
            if not isinstance(device_data, dict):
                continue
            if host_recovery_issue_id(device_id) == issue_id:
                return _RepairTarget(entry, device_id, device_data, "host_recovery")
            for failure in HEALTH_FAILURE_TRANSLATIONS:
                if device_health_issue_id(device_id, failure) == issue_id:
                    return _RepairTarget(entry, device_id, device_data, failure)
    return None


def _validation_error_key(error_type: str | None) -> str:
    return {
        CannotConnect.__name__: "cannot_connect",
        InvalidAuth.__name__: "invalid_auth",
        EmptyDpsList.__name__: "empty_dps",
    }.get(str(error_type), "unknown")


class _BaseDeviceRepairFlow(RepairsFlow):
    """Shared validated persistence helpers for LocalTuya Repairs."""

    def __init__(self, target: _RepairTarget) -> None:
        self._target = target
        super().__init__()

    def _placeholders(self) -> dict[str, str]:
        return {"device_name": self._target.device_name}

    def _current_device_data(self) -> dict[str, Any] | None:
        devices = self._target.entry.data.get(CONF_DEVICES, {})
        if not isinstance(devices, dict):
            return None
        current = devices.get(self._target.device_id)
        return copy.deepcopy(current) if isinstance(current, dict) else None

    async def _persist_validated_device(
        self,
        candidate: dict[str, Any],
        *,
        root_updates: dict[str, Any] | None = None,
    ) -> str | None:
        """Validate candidate credentials/protocol then atomically persist them."""
        probe_data = copy.deepcopy(candidate)
        probe_data[CONF_DEVICE_ID] = self._target.device_id
        try:
            dps_strings, resolved_protocol = await validate_input(self.hass, probe_data)
        except CannotConnect:
            return "cannot_connect"
        except InvalidAuth:
            return "invalid_auth"
        except EmptyDpsList:
            return "empty_dps"
        except Exception:  # noqa: BLE001 - Repair UI must fail closed.
            return "unknown"

        candidate[CONF_PROTOCOL_VERSION] = resolved_protocol
        candidate[CONF_DPS_STRINGS] = list(dps_strings)
        new_data = copy.deepcopy(dict(self._target.entry.data))
        new_data[CONF_DEVICES][self._target.device_id] = candidate
        if root_updates:
            new_data.update(copy.deepcopy(root_updates))
        new_data[ATTR_UPDATED_AT] = str(int(asyncio.get_running_loop().time() * 1000))
        self.hass.config_entries.async_update_entry(self._target.entry, data=new_data)
        async_clear_device_health_issues(self.hass, self._target.device_id)
        async_clear_host_recovery_issue(self.hass, self._target.device_id)

        reload_entry = getattr(self.hass.config_entries, "async_reload", None)
        if callable(reload_entry) and getattr(self._target.entry, "entry_id", None):
            await reload_entry(self._target.entry.entry_id)
        return None


class HostRecoveryRepairFlow(_BaseDeviceRepairFlow):
    """Repair a LocalTuya device whose LAN host cannot be validated."""

    def _manual_host_form(
        self,
        *,
        user_input: dict[str, str] | None = None,
        errors: dict[str, str] | None = None,
        suggested_host: str | None = None,
    ) -> RepairsFlowResult:
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

    async def async_step_init(self, user_input=None) -> RepairsFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["rediscover", "manual_host"],
            description_placeholders=self._placeholders(),
        )

    async def _async_validate_current_host(self) -> str | None:
        current = self._current_device_data()
        if current is None:
            return "device_not_found"
        return await self._persist_validated_device(current)

    async def _async_apply_candidate(
        self,
        candidate_host: str,
        *,
        product_key: str | None = None,
    ) -> str | None:
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
            async_clear_device_health_issues(self.hass, self._target.device_id)
            async_clear_host_recovery_issue(self.hass, self._target.device_id)
            return None
        if result.outcome is HostRecoveryOutcome.VALIDATION_FAILED:
            return _validation_error_key(result.validation_error_type)
        if result.outcome is HostRecoveryOutcome.STALE:
            return "stale"
        if result.outcome is HostRecoveryOutcome.INVALID_ADDRESS:
            return "invalid_host"
        return "device_not_found"

    async def async_step_rediscover(self, user_input=None) -> RepairsFlowResult:
        discovery = self.hass.data.get(DOMAIN, {}).get(DATA_DISCOVERY)
        request_discovery = getattr(discovery, "async_request_discovery", None)
        if not callable(request_discovery):
            return self._manual_host_form(errors={"base": "discovery_unavailable"})
        try:
            await request_discovery()
            await asyncio.sleep(_DISCOVERY_SETTLE_SECONDS)
        except Exception:  # noqa: BLE001
            return self._manual_host_form(errors={"base": "discovery_failed"})

        devices = getattr(discovery, "devices", {})
        discovery_id = (
            self._target.device_data.get("gateway_id")
            or self._target.device_id
        )
        candidate = devices.get(discovery_id) if isinstance(devices, dict) else None
        if not isinstance(candidate, dict) or not candidate.get("ip"):
            return self._manual_host_form(errors={"base": "device_not_found"})

        host = str(candidate["ip"])
        error = await self._async_apply_candidate(
            host,
            product_key=candidate.get("productKey") or candidate.get(CONF_PRODUCT_KEY),
        )
        if error is not None:
            return self._manual_host_form(
                errors={"base": error},
                suggested_host=host,
            )
        return self.async_create_entry(title="", data={})

    async def async_step_manual_host(self, user_input=None) -> RepairsFlowResult:
        if user_input is not None:
            error = await self._async_apply_candidate(user_input.get(CONF_HOST, ""))
            if error is None:
                return self.async_create_entry(title="", data={})
            return self._manual_host_form(user_input=user_input, errors={"base": error})
        return self._manual_host_form()


class DeviceHealthRepairFlow(_BaseDeviceRepairFlow):
    """Repair credentials, protocol selection and non-host health failures."""

    async def async_step_init(self, user_input=None) -> RepairsFlowResult:
        failure = self._target.failure
        options = {
            "auth_or_protocol": ["refresh_credentials", "manual_credentials", "select_protocol", "retry"],
            "protocol_not_detected": ["select_protocol", "retry"],
            "empty_dps": ["retry", "select_protocol"],
            "invalid_configuration": ["manual_credentials", "select_protocol", "retry"],
            "probe_error": ["retry", "select_protocol"],
        }.get(failure, ["retry"])
        return self.async_show_menu(
            step_id="init",
            menu_options=options,
            description_placeholders=self._placeholders(),
        )

    async def async_step_retry(self, user_input=None) -> RepairsFlowResult:
        current = self._current_device_data()
        if current is None:
            return self.async_abort(reason="device_not_found")
        error = await self._persist_validated_device(current)
        if error is None:
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="retry",
            data_schema=vol.Schema({}),
            errors={"base": error},
            description_placeholders=self._placeholders(),
        )

    async def async_step_manual_credentials(self, user_input=None) -> RepairsFlowResult:
        current = self._current_device_data()
        if current is None:
            return self.async_abort(reason="device_not_found")
        errors = {}
        if user_input is not None:
            local_key = str(user_input.get(CONF_LOCAL_KEY, "")).strip()
            if not local_key:
                errors["base"] = "invalid_auth"
            else:
                candidate = copy.deepcopy(current)
                candidate[CONF_LOCAL_KEY] = local_key
                error = await self._persist_validated_device(candidate)
                if error is None:
                    return self.async_create_entry(title="", data={})
                errors["base"] = error
        return self.async_show_form(
            step_id="manual_credentials",
            data_schema=vol.Schema({vol.Required(CONF_LOCAL_KEY): str}),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    async def async_step_refresh_credentials(self, user_input=None) -> RepairsFlowResult:
        """Refresh a local key through the saved QR authorization, then validate it."""
        current = self._current_device_data()
        if current is None:
            return self.async_abort(reason="device_not_found")
        auth = self._target.entry.data.get(CONF_QR_AUTH)
        if not isinstance(auth, dict) or not auth:
            return self.async_show_form(
                step_id="refresh_credentials",
                data_schema=vol.Schema({}),
                errors={"base": "qr_account_not_linked"},
                description_placeholders=self._placeholders(),
            )

        try:
            client = QrCloudClient(self.hass, auth)
            devices = await client.async_get_devices()
            cloud_device = devices.get(self._target.device_id)
            if not isinstance(cloud_device, dict):
                raise QrProvisioningError("device_not_found", "device not found")
            is_child = bool(current.get("node_id"))
            refreshed_key = str(
                (cloud_device.get("gateway_local_key") if is_child else None)
                or cloud_device.get(CONF_LOCAL_KEY)
                or ""
            ).strip()
            if not refreshed_key:
                raise QrProvisioningError("invalid_auth", "local key unavailable")
        except QrProvisioningError as ex:
            error = "qr_reauth_required" if ex.reason == "qr_reauth_required" else "credential_refresh_failed"
            return self.async_show_form(
                step_id="refresh_credentials",
                data_schema=vol.Schema({}),
                errors={"base": error},
                description_placeholders=self._placeholders(),
            )
        except Exception:  # noqa: BLE001
            return self.async_show_form(
                step_id="refresh_credentials",
                data_schema=vol.Schema({}),
                errors={"base": "credential_refresh_failed"},
                description_placeholders=self._placeholders(),
            )

        candidate = copy.deepcopy(current)
        candidate[CONF_LOCAL_KEY] = refreshed_key
        error = await self._persist_validated_device(
            candidate,
            root_updates={CONF_QR_AUTH: client.auth},
        )
        if error is None:
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="refresh_credentials",
            data_schema=vol.Schema({}),
            errors={"base": error},
            description_placeholders=self._placeholders(),
        )

    async def async_step_select_protocol(self, user_input=None) -> RepairsFlowResult:
        current = self._current_device_data()
        if current is None:
            return self.async_abort(reason="device_not_found")
        errors = {}
        choices = (PROTOCOL_AUTO, *SUPPORTED_PROTOCOL_VERSIONS)
        if user_input is not None:
            candidate = copy.deepcopy(current)
            candidate[CONF_PROTOCOL_VERSION] = str(user_input[CONF_PROTOCOL_VERSION])
            error = await self._persist_validated_device(candidate)
            if error is None:
                return self.async_create_entry(title="", data={})
            errors["base"] = error
        default = str(current.get(CONF_PROTOCOL_VERSION, PROTOCOL_AUTO))
        if default not in choices:
            default = PROTOCOL_AUTO
        return self.async_show_form(
            step_id="select_protocol",
            data_schema=vol.Schema(
                {vol.Required(CONF_PROTOCOL_VERSION, default=default): vol.In(choices)}
            ),
            errors=errors,
            description_placeholders=self._placeholders(),
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the correct interactive fix flow for a LocalTuya Repair issue."""
    del data
    target = _find_repair_target(hass, issue_id)
    if target is None:
        return ConfirmRepairFlow()
    if target.failure in {"host_recovery", "host_unreachable"}:
        return HostRecoveryRepairFlow(target)
    return DeviceHealthRepairFlow(target)
