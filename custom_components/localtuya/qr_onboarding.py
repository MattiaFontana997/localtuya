"""QR onboarding and on-demand Tuya account provisioning for LocalTuya."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from typing import Any

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_NAME,
    CONF_REGION,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    QrCodeSelector,
    QrCodeSelectorConfig,
    QrErrorCorrectionLevel,
)
from tuya_sharing import LoginControl, Manager, SharingTokenListener

from .const import (
    ATTR_UPDATED_AT,
    CONF_DPS_STRINGS,
    CONF_ENABLE_DEBUG,
    CONF_LOCAL_KEY,
    CONF_NO_CLOUD,
    CONF_PRODUCT_KEY,
    CONF_PROTOCOL_VERSION,
    CONF_USER_ID,
    DATA_DEVICE_CATALOG,
    DATA_DISCOVERY,
    DOMAIN,
)
from .mapping_resolver import resolve_entity_candidates
from .device_mapper import MappingConfidence

_LOGGER = logging.getLogger(__name__)

CONF_QR_AUTH = "qr_auth"
CONF_QR_USER_CODE = "user_code"
CONF_QR_TERMINAL_ID = "terminal_id"
CONF_QR_ENDPOINT = "endpoint"
CONF_QR_TOKEN_INFO = "token_info"

TUYA_CLIENT_ID = "HA_3y9q4ak7g4ephrvke"
TUYA_SCHEMA = "haauthorize"

_QR_TOKEN_FIELDS = (
    "t",
    "uid",
    "expire_time",
    "access_token",
    "refresh_token",
)


class QrProvisioningError(Exception):
    """A QR provisioning operation could not be completed safely."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail


def _token_info(value: dict[str, Any]) -> dict[str, Any]:
    """Keep only the token fields required by tuya-device-sharing-sdk."""
    return {
        key: value[key]
        for key in _QR_TOKEN_FIELDS
        if key in value
    }


class _TokenCapture(SharingTokenListener):
    """Capture refreshed sharing tokens without starting cloud polling."""

    def __init__(self, auth: dict[str, Any]) -> None:
        self._auth = auth

    def update_token(self, token_info: dict[str, Any]) -> None:
        """Store refreshed token material in the in-memory account link."""
        self._auth[CONF_QR_TOKEN_INFO] = _token_info(token_info)


class QrCloudClient:
    """Short-lived Tuya sharing client used only for provisioning/sync."""

    def __init__(
        self,
        hass,
        auth: dict[str, Any] | None = None,
    ) -> None:
        self.hass = hass
        self._login_control = LoginControl()
        self._auth = copy.deepcopy(auth or {})
        self._user_code = self._auth.get(CONF_QR_USER_CODE)
        self._qr_token: str | None = None
        self._manager: Manager | None = None
        self.last_error: dict[str, Any] = {}

    @property
    def auth(self) -> dict[str, Any]:
        """Return the current account link, including refreshed tokens."""
        return copy.deepcopy(self._auth)

    @property
    def is_authenticated(self) -> bool:
        """Return whether enough persisted state exists to create a Manager."""
        return all(
            self._auth.get(key)
            for key in (
                CONF_QR_USER_CODE,
                CONF_QR_TERMINAL_ID,
                CONF_QR_ENDPOINT,
                CONF_QR_TOKEN_INFO,
            )
        )

    async def async_generate_qr(self, user_code: str) -> str | None:
        """Generate a Smart Life/Tuya QR token for the supplied User Code."""
        user_code = str(user_code or "").strip()
        if not user_code:
            self.last_error = {"msg": "User Code is required", "code": "missing_user_code"}
            return None

        response = await self.hass.async_add_executor_job(
            self._login_control.qr_code,
            TUYA_CLIENT_ID,
            TUYA_SCHEMA,
            user_code,
        )

        if not isinstance(response, dict) or not response.get("success", False):
            self.last_error = {
                "msg": str((response or {}).get("msg", "Unable to generate QR code")),
                "code": str((response or {}).get("code", "qr_failed")),
            }
            return None

        result = response.get("result")
        token = result.get("qrcode") if isinstance(result, dict) else None
        if not isinstance(token, str) or not token:
            self.last_error = {"msg": "Tuya returned an empty QR token", "code": "qr_failed"}
            return None

        self._user_code = user_code
        self._qr_token = token
        self.last_error = {}
        return token

    async def async_login(self) -> bool:
        """Exchange the scanned QR token for a renewable sharing session."""
        if not self._user_code or not self._qr_token:
            self.last_error = {"msg": "Generate and scan the QR code first", "code": "qr_missing"}
            return False

        success, info = await self.hass.async_add_executor_job(
            self._login_control.login_result,
            self._qr_token,
            TUYA_CLIENT_ID,
            self._user_code,
        )

        if not success or not isinstance(info, dict):
            info = info if isinstance(info, dict) else {}
            self.last_error = {
                "msg": str(info.get("msg", "QR login not completed")),
                "code": str(info.get("code", "login_failed")),
            }
            return False

        try:
            self._auth = {
                CONF_QR_USER_CODE: self._user_code,
                CONF_QR_TERMINAL_ID: info[CONF_QR_TERMINAL_ID],
                CONF_QR_ENDPOINT: info[CONF_QR_ENDPOINT],
                CONF_QR_TOKEN_INFO: _token_info(info),
            }
        except KeyError as exc:
            self.last_error = {
                "msg": f"Tuya login response is missing {exc.args[0]}",
                "code": "invalid_login_response",
            }
            return False

        self.last_error = {}
        return True

    def _build_manager(self) -> Manager:
        """Create the sharing Manager from the persisted renewable session."""
        if not self.is_authenticated:
            raise QrProvisioningError("qr_reauth_required", "Tuya account authorization is incomplete")

        token_listener = _TokenCapture(self._auth)
        return Manager(
            TUYA_CLIENT_ID,
            self._auth[CONF_QR_USER_CODE],
            self._auth[CONF_QR_TERMINAL_ID],
            self._auth[CONF_QR_ENDPOINT],
            self._auth[CONF_QR_TOKEN_INFO],
            token_listener,
        )

    async def async_get_devices(self) -> dict[str, dict[str, Any]]:
        """Refresh the account device cache once and return provisioning metadata."""
        manager = self._build_manager()
        try:
            await self.hass.async_add_executor_job(manager.update_device_cache)
        except Exception as exc:
            message = str(exc)
            reason = "qr_reauth_required" if "sign invalid" in message.lower() else "qr_cloud_unavailable"
            raise QrProvisioningError(reason, message) from exc

        self._manager = manager
        devices: dict[str, dict[str, Any]] = {}

        for device in manager.device_map.values():
            device_id = str(getattr(device, "id", "") or "").strip()
            if not device_id:
                continue

            local_key = str(getattr(device, "local_key", "") or "").strip()
            product_id = str(getattr(device, "product_id", "") or "").strip()
            node_id = str(getattr(device, "node_id", "") or "").strip()

            devices[device_id] = {
                "id": device_id,
                CONF_NAME: str(getattr(device, "name", "") or "").strip(),
                CONF_LOCAL_KEY: local_key,
                "product_id": product_id,
                "product_name": str(getattr(device, "product_name", "") or "").strip(),
                "category": str(getattr(device, "category", "") or "").strip(),
                "online": bool(getattr(device, "online", False)),
                "support_local": bool(getattr(device, "support_local", False)),
                "node_id": node_id,
            }

        return devices

    async def async_get_datamodel(self, device_id: str) -> list[dict[str, Any]]:
        """Fetch local-capable DP metadata for one selected device."""
        if self._manager is None:
            self._manager = self._build_manager()

        try:
            response = await self.hass.async_add_executor_job(
                self._manager.customer_api.get,
                f"/v1.0/m/life/devices/{device_id}/status",
            )
        except Exception as exc:
            _LOGGER.debug("QR datamodel request failed for %s: %s", device_id, exc)
            return []

        if not isinstance(response, dict):
            return []

        result = response.get("result")
        if isinstance(result, dict):
            response = result

        entries = response.get("dpStatusRelationDTOS")
        if not isinstance(entries, list):
            return []

        model: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("supportLocal", False):
                continue
            try:
                dp_id = int(entry.get("dpId"))
            except (TypeError, ValueError):
                continue
            if dp_id <= 0:
                continue
            model.append(
                {
                    "id": dp_id,
                    "code": str(entry.get("dpCode", "") or ""),
                    "type": str(entry.get("valueType", "") or ""),
                    "values": entry.get("valueDesc", "{}"),
                    "enumMap": entry.get("enumMappingMap", {}),
                }
            )
        return model


def _datamodel_mapping(model: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Convert sharing datamodel entries into LocalTuya mapper metadata."""
    result: dict[str, dict[str, Any]] = {}
    for entry in model:
        try:
            dp_id = int(entry.get("id"))
        except (TypeError, ValueError):
            continue
        values: Any = entry.get("values", {})
        if isinstance(values, str):
            try:
                values = json.loads(values)
            except (TypeError, ValueError, json.JSONDecodeError):
                values = {}
        if not isinstance(values, dict):
            values = {}
        enum_map = entry.get("enumMap")
        if isinstance(enum_map, dict) and enum_map and "range" not in values:
            values = {**values, "range": list(enum_map)}
        result[str(dp_id)] = {
            "dp_id": dp_id,
            "code": entry.get("code", ""),
            "type": entry.get("type", ""),
            "values": values,
        }
    return result


async def _async_discovery_snapshot(hass) -> dict[str, dict[str, Any]]:
    """Request a fresh LAN discovery snapshot without depending on cloud IP data."""
    domain_data = hass.data.get(DOMAIN, {})
    discovery = domain_data.get(DATA_DISCOVERY)

    if discovery is not None:
        try:
            await discovery.async_request_discovery()
            await asyncio.sleep(1.0)
        except Exception as exc:
            _LOGGER.debug("Active Tuya LAN discovery refresh failed: %s", exc)
        devices = getattr(discovery, "devices", {})
        if isinstance(devices, dict):
            return copy.deepcopy(devices)

    from .discovery import discover

    try:
        devices = await discover(hass=hass)
    except Exception as exc:
        raise QrProvisioningError("discovery_failed", str(exc)) from exc
    return devices if isinstance(devices, dict) else {}


def _find_discovered_device(
    devices: dict[str, dict[str, Any]],
    device_id: str,
) -> dict[str, Any] | None:
    """Find one device by discovery dictionary key or gwId/id payload."""
    direct = devices.get(device_id)
    if isinstance(direct, dict):
        return copy.deepcopy(direct)

    for candidate in devices.values():
        if not isinstance(candidate, dict):
            continue
        found_id = candidate.get("gwId") or candidate.get("id")
        if found_id == device_id:
            return copy.deepcopy(candidate)
    return None


async def async_prepare_qr_device(
    hass,
    cloud: QrCloudClient,
    cloud_device: dict[str, Any],
) -> tuple[dict[str, Any], list[Any]]:
    """Resolve cloud identity, LAN connectivity, protocol and automatic mapping."""
    device_id = str(cloud_device.get("id") or "").strip()
    local_key = str(cloud_device.get(CONF_LOCAL_KEY) or "").strip()

    if not device_id or not local_key:
        raise QrProvisioningError("qr_device_not_local", "Device ID/local_key is not available")
    if cloud_device.get("node_id"):
        raise QrProvisioningError("qr_subdevice_not_supported", "The selected device is a hub child device")
    if not cloud_device.get("support_local", True):
        raise QrProvisioningError("qr_device_not_local", "Tuya marks this device as cloud-only")

    discovered_devices = await _async_discovery_snapshot(hass)
    discovered = _find_discovered_device(discovered_devices, device_id)
    if discovered is None or not discovered.get("ip"):
        raise QrProvisioningError(
            "qr_device_not_on_lan",
            "The selected device was not found on the Home Assistant LAN",
        )

    model = await cloud.async_get_datamodel(device_id)
    merged_discovery = {
        **discovered,
        **cloud_device,
        "mapping": _datamodel_mapping(model),
    }
    merged_discovery["ip"] = discovered.get("ip")
    merged_discovery["gwId"] = device_id

    from .config_flow import PROTOCOL_AUTO, validate_input

    device_data: dict[str, Any] = {
        CONF_FRIENDLY_NAME: (
            cloud_device.get(CONF_NAME)
            or cloud_device.get("product_name")
            or device_id
        ),
        CONF_HOST: discovered["ip"],
        CONF_DEVICE_ID: device_id,
        CONF_LOCAL_KEY: local_key,
        CONF_PROTOCOL_VERSION: PROTOCOL_AUTO,
        CONF_ENABLE_DEBUG: False,
        "product_id": cloud_device.get("product_id") or "",
    }

    product_key = discovered.get("productKey") or cloud_device.get("product_id")
    if product_key:
        device_data[CONF_PRODUCT_KEY] = str(product_key)

    dps_strings, resolved_protocol = await validate_input(hass, device_data)
    device_data[CONF_PROTOCOL_VERSION] = resolved_protocol
    device_data[CONF_DPS_STRINGS] = list(dps_strings)

    detected_ids: set[int] = set()
    for raw in dps_strings:
        try:
            detected_ids.add(int(str(raw).split(" ", 1)[0]))
        except (TypeError, ValueError):
            continue

    catalog_client = hass.data.get(DOMAIN, {}).get(DATA_DEVICE_CATALOG)
    candidates = resolve_entity_candidates(
        merged_discovery,
        None,
        detected_ids,
        catalog_client=catalog_client,
    )

    high = [
        copy.deepcopy(candidate.config)
        for candidate in candidates
        if candidate.confidence == MappingConfidence.HIGH
    ]
    medium = [
        candidate
        for candidate in candidates
        if candidate.confidence == MappingConfidence.MEDIUM
    ]

    device_data[CONF_ENTITIES] = high
    return device_data, medium


def _candidate_options(candidates: list[Any]) -> dict[str, str]:
    """Build stable labels for medium-confidence mapping review."""
    return {
        str(index): (
            f"{candidate.config.get(CONF_FRIENDLY_NAME, 'Tuya entity')}"
            f" — {candidate.platform} · DP {candidate.primary_dp}"
        )
        for index, candidate in enumerate(candidates)
    }


def _base_entry_data(auth: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a backward-compatible LocalTuya root config entry."""
    return {
        CONF_REGION: "eu",
        CONF_CLIENT_ID: "",
        CONF_CLIENT_SECRET: "",
        CONF_USER_ID: "",
        CONF_USERNAME: DOMAIN,
        CONF_NO_CLOUD: True,
        CONF_QR_AUTH: copy.deepcopy(auth or {}),
        CONF_DEVICES: {},
    }


class QrConfigFlowMixin:
    """Config-flow steps for recommended QR onboarding and manual fallback."""

    async def async_step_qr_login(self, user_input=None):
        """Collect the Smart Life/Tuya User Code and generate a QR token."""
        errors = {}
        placeholders = {}
        if user_input is not None:
            self._qr_cloud = QrCloudClient(self.hass)
            token = await self._qr_cloud.async_generate_qr(user_input[CONF_QR_USER_CODE])
            if token:
                self._qr_token = token
                return await self.async_step_qr_scan()
            errors["base"] = "qr_login_error"
            placeholders = self._qr_cloud.last_error

        return self.async_show_form(
            step_id="qr_login",
            data_schema=vol.Schema({vol.Required(CONF_QR_USER_CODE): str}),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_qr_scan(self, user_input=None):
        """Display the QR code and complete account authorization after scanning."""
        cloud = getattr(self, "_qr_cloud", None)
        token = getattr(self, "_qr_token", None)
        if cloud is None or not token:
            return await self.async_step_qr_login()

        if user_input is None:
            return self.async_show_form(
                step_id="qr_scan",
                data_schema=vol.Schema(
                    {
                        vol.Optional("QR"): QrCodeSelector(
                            config=QrCodeSelectorConfig(
                                data=f"tuyaSmart--qrLogin?token={token}",
                                scale=5,
                                error_correction_level=QrErrorCorrectionLevel.QUARTILE,
                            )
                        )
                    }
                ),
            )

        if not await cloud.async_login():
            refreshed = await cloud.async_generate_qr(cloud._user_code)
            if refreshed:
                self._qr_token = refreshed
            return self.async_show_form(
                step_id="qr_scan",
                data_schema=vol.Schema(
                    {
                        vol.Optional("QR"): QrCodeSelector(
                            config=QrCodeSelectorConfig(
                                data=f"tuyaSmart--qrLogin?token={self._qr_token}",
                                scale=5,
                                error_correction_level=QrErrorCorrectionLevel.QUARTILE,
                            )
                        )
                    }
                ),
                errors={"base": "qr_login_error"},
                description_placeholders=cloud.last_error,
            )

        try:
            self._qr_devices = await cloud.async_get_devices()
        except QrProvisioningError as exc:
            return self.async_abort(reason=exc.reason)
        self._qr_auth = cloud.auth
        return await self.async_step_qr_choose_device()

    async def async_step_qr_choose_device(self, user_input=None):
        """Choose a locally controllable device from the linked Tuya account."""
        devices = getattr(self, "_qr_devices", {})
        eligible = {
            device_id: device
            for device_id, device in devices.items()
            if device.get(CONF_LOCAL_KEY)
            and not device.get("node_id")
            and device.get("support_local", True)
        }
        if not eligible:
            return self.async_abort(reason="qr_no_local_devices")

        if user_input is not None:
            selected = user_input[CONF_DEVICE_ID]
            cloud_device = eligible[selected]
            try:
                self._qr_device_data, self._qr_medium_candidates = await async_prepare_qr_device(
                    self.hass,
                    self._qr_cloud,
                    cloud_device,
                )
            except QrProvisioningError as exc:
                return self.async_show_form(
                    step_id="qr_choose_device",
                    data_schema=self._qr_device_schema(eligible),
                    errors={"base": exc.reason},
                    description_placeholders={"msg": exc.detail},
                )

            if self._qr_medium_candidates:
                return await self.async_step_qr_mapping_review()
            if not self._qr_device_data.get(CONF_ENTITIES):
                return self.async_abort(reason="qr_mapping_not_found")
            return await self._async_finish_initial_qr()

        return self.async_show_form(
            step_id="qr_choose_device",
            data_schema=self._qr_device_schema(eligible),
        )

    @staticmethod
    def _qr_device_schema(devices: dict[str, dict[str, Any]]):
        labels = {
            device_id: (
                f"{device.get(CONF_NAME) or device_id}"
                f" ({device.get('product_name') or device.get('category') or 'Tuya'})"
            )
            for device_id, device in devices.items()
        }
        return vol.Schema({vol.Required(CONF_DEVICE_ID): vol.In(labels)})

    async def async_step_qr_mapping_review(self, user_input=None):
        """Review only mappings that are not high-confidence."""
        candidates = getattr(self, "_qr_medium_candidates", [])
        device_data = getattr(self, "_qr_device_data", None)
        if not isinstance(device_data, dict):
            return await self.async_step_qr_choose_device()

        options = _candidate_options(candidates)
        if user_input is not None:
            for index in user_input.get("qr_mapping_selection", []):
                try:
                    candidate = candidates[int(index)]
                except (ValueError, IndexError):
                    continue
                device_data[CONF_ENTITIES].append(copy.deepcopy(candidate.config))
            if not device_data[CONF_ENTITIES]:
                return self.async_show_form(
                    step_id="qr_mapping_review",
                    data_schema=vol.Schema(
                        {vol.Required("qr_mapping_selection", default=list(options)): cv.multi_select(options)}
                    ),
                    errors={"base": "qr_mapping_required"},
                )
            return await self._async_finish_initial_qr()

        return self.async_show_form(
            step_id="qr_mapping_review",
            data_schema=vol.Schema(
                {vol.Required("qr_mapping_selection", default=list(options)): cv.multi_select(options)}
            ),
        )

    async def _async_finish_initial_qr(self):
        """Create the first LocalTuya entry; runtime remains LAN-only."""
        auth = self._qr_cloud.auth
        data = _base_entry_data(auth)
        device_data = copy.deepcopy(self._qr_device_data)
        device_id = device_data[CONF_DEVICE_ID]
        data[CONF_DEVICES][device_id] = device_data

        uid = auth.get(CONF_QR_TOKEN_INFO, {}).get("uid")
        if uid:
            await self.async_set_unique_id(f"qr_{uid}")
            self._abort_if_unique_id_configured()

        return self.async_create_entry(title=DOMAIN, data=data)

    async def async_step_manual_device(self, user_input=None):
        """Advanced first-device setup without any Tuya account link."""
        from .config_flow import DEVICE_SCHEMA, schema_defaults, validate_input, async_get_entity_candidates

        errors = {}
        if user_input is not None:
            try:
                dps_strings, resolved = await validate_input(self.hass, user_input)
                device_data = dict(user_input)
                device_data[CONF_PROTOCOL_VERSION] = resolved
                device_data[CONF_DPS_STRINGS] = list(dps_strings)
                discovery = await _async_discovery_snapshot(self.hass)
                candidates = await async_get_entity_candidates(
                    self.hass,
                    device_data,
                    discovery,
                    dps_strings,
                )
                device_data[CONF_ENTITIES] = [
                    copy.deepcopy(candidate.config)
                    for candidate in candidates
                    if candidate.confidence == MappingConfidence.HIGH
                ]
                if not device_data[CONF_ENTITIES]:
                    errors["base"] = "qr_mapping_not_found"
                else:
                    data = _base_entry_data()
                    data[CONF_DEVICES][device_data[CONF_DEVICE_ID]] = device_data
                    return self.async_create_entry(title=DOMAIN, data=data)
            except Exception as exc:
                _LOGGER.debug("Manual initial provisioning failed: %s", exc)
                errors["base"] = "cannot_connect"

        defaults = {
            CONF_PROTOCOL_VERSION: "auto",
            CONF_ENABLE_DEBUG: False,
        }
        return self.async_show_form(
            step_id="manual_device",
            data_schema=schema_defaults(DEVICE_SCHEMA, **defaults),
            errors=errors,
        )


class QrOptionsFlowMixin:
    """Options-flow steps for future device sync without repeating QR login."""

    async def async_step_add_device_method(self, user_input=None):
        """Choose linked-account provisioning or account-management actions."""
        return self.async_show_menu(
            step_id="add_device_method",
            menu_options=[
                "qr_add_device",
                "manual_add_device",
                "qr_relink",
                "qr_disconnect",
            ],
        )

    async def async_step_manual_add_device(self, user_input=None):
        """Enter the existing manual/LAN device flow even when QR is linked."""
        self._manual_add_in_progress = True
        return await self.async_step_add_device()

    async def async_step_qr_add_device(self, user_input=None):
        """Refresh Tuya devices on demand and add one new LAN device."""
        auth = self.config_entry.data.get(CONF_QR_AUTH)
        if not isinstance(auth, dict) or not auth:
            return self.async_abort(reason="qr_not_linked")

        if not getattr(self, "_qr_devices", None):
            self._qr_cloud = QrCloudClient(self.hass, auth)
            try:
                self._qr_devices = await self._qr_cloud.async_get_devices()
            except QrProvisioningError as exc:
                return self.async_abort(reason=exc.reason)
            self._persist_qr_auth(self._qr_cloud.auth)

        configured = set(self.config_entry.data.get(CONF_DEVICES, {}))
        eligible = {
            device_id: device
            for device_id, device in self._qr_devices.items()
            if device_id not in configured
            and device.get(CONF_LOCAL_KEY)
            and not device.get("node_id")
            and device.get("support_local", True)
        }
        if not eligible:
            return self.async_abort(reason="qr_no_new_local_devices")

        if user_input is not None:
            selected = user_input[CONF_DEVICE_ID]
            try:
                self._qr_device_data, self._qr_medium_candidates = await async_prepare_qr_device(
                    self.hass,
                    self._qr_cloud,
                    eligible[selected],
                )
            except QrProvisioningError as exc:
                return self.async_show_form(
                    step_id="qr_add_device",
                    data_schema=QrConfigFlowMixin._qr_device_schema(eligible),
                    errors={"base": exc.reason},
                    description_placeholders={"msg": exc.detail},
                )

            if self._qr_medium_candidates:
                return await self.async_step_qr_add_mapping_review()
            if not self._qr_device_data.get(CONF_ENTITIES):
                return self.async_abort(reason="qr_mapping_not_found")
            return self._finish_qr_added_device()

        return self.async_show_form(
            step_id="qr_add_device",
            data_schema=QrConfigFlowMixin._qr_device_schema(eligible),
        )

    async def async_step_qr_add_mapping_review(self, user_input=None):
        """Review medium-confidence mappings before saving a newly synced device."""
        candidates = getattr(self, "_qr_medium_candidates", [])
        device_data = getattr(self, "_qr_device_data", None)
        if not isinstance(device_data, dict):
            return await self.async_step_qr_add_device()

        options = _candidate_options(candidates)
        if user_input is not None:
            for index in user_input.get("qr_mapping_selection", []):
                try:
                    candidate = candidates[int(index)]
                except (ValueError, IndexError):
                    continue
                device_data[CONF_ENTITIES].append(copy.deepcopy(candidate.config))
            if not device_data[CONF_ENTITIES]:
                return self.async_show_form(
                    step_id="qr_add_mapping_review",
                    data_schema=vol.Schema(
                        {vol.Required("qr_mapping_selection", default=list(options)): cv.multi_select(options)}
                    ),
                    errors={"base": "qr_mapping_required"},
                )
            return self._finish_qr_added_device()

        return self.async_show_form(
            step_id="qr_add_mapping_review",
            data_schema=vol.Schema(
                {vol.Required("qr_mapping_selection", default=list(options)): cv.multi_select(options)}
            ),
        )

    def _finish_qr_added_device(self):
        """Persist a QR-provisioned device; its runtime is fully LAN-based."""
        new_data = copy.deepcopy(dict(self.config_entry.data))
        device_data = copy.deepcopy(self._qr_device_data)
        new_data.setdefault(CONF_DEVICES, {})[device_data[CONF_DEVICE_ID]] = device_data
        new_data[CONF_QR_AUTH] = self._qr_cloud.auth
        new_data[ATTR_UPDATED_AT] = str(int(__import__("time").time() * 1000))
        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
        return self.async_create_entry(title="", data={})

    def _persist_qr_auth(self, auth: dict[str, Any]) -> None:
        """Persist a refreshed sharing token after an explicit sync action."""
        new_data = copy.deepcopy(dict(self.config_entry.data))
        new_data[CONF_QR_AUTH] = copy.deepcopy(auth)
        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)

    async def async_step_qr_relink(self, user_input=None):
        """Generate a new QR authorization for an existing LocalTuya entry."""
        errors = {}
        placeholders = {}
        current = self.config_entry.data.get(CONF_QR_AUTH, {})
        default_code = (
            current.get(CONF_QR_USER_CODE, "")
            if isinstance(current, dict)
            else ""
        )
        if user_input is not None:
            self._qr_cloud = QrCloudClient(self.hass)
            token = await self._qr_cloud.async_generate_qr(
                user_input[CONF_QR_USER_CODE]
            )
            if token:
                self._qr_token = token
                return await self.async_step_qr_relink_scan()
            errors["base"] = "qr_login_error"
            placeholders = self._qr_cloud.last_error

        return self.async_show_form(
            step_id="qr_relink",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_QR_USER_CODE,
                        default=default_code,
                    ): str
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_qr_relink_scan(self, user_input=None):
        """Complete a replacement QR authorization and persist it."""
        cloud = getattr(self, "_qr_cloud", None)
        token = getattr(self, "_qr_token", None)
        if cloud is None or not token:
            return await self.async_step_qr_relink()

        if user_input is None:
            return self.async_show_form(
                step_id="qr_relink_scan",
                data_schema=vol.Schema(
                    {
                        vol.Optional("QR"): QrCodeSelector(
                            config=QrCodeSelectorConfig(
                                data=f"tuyaSmart--qrLogin?token={token}",
                                scale=5,
                                error_correction_level=(
                                    QrErrorCorrectionLevel.QUARTILE
                                ),
                            )
                        )
                    }
                ),
            )

        if not await cloud.async_login():
            return self.async_show_form(
                step_id="qr_relink_scan",
                data_schema=vol.Schema(
                    {
                        vol.Optional("QR"): QrCodeSelector(
                            config=QrCodeSelectorConfig(
                                data=f"tuyaSmart--qrLogin?token={token}",
                                scale=5,
                                error_correction_level=(
                                    QrErrorCorrectionLevel.QUARTILE
                                ),
                            )
                        )
                    }
                ),
                errors={"base": "qr_login_error"},
                description_placeholders=cloud.last_error,
            )

        self._persist_qr_auth(cloud.auth)
        return self.async_create_entry(title="", data={})

    async def async_step_qr_disconnect(self, user_input=None):
        """Forget the Tuya account link while leaving all LAN devices intact."""
        if user_input is not None and user_input.get("confirm", False):
            new_data = copy.deepcopy(dict(self.config_entry.data))
            new_data[CONF_QR_AUTH] = {}
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="qr_disconnect",
            data_schema=vol.Schema(
                {vol.Required("confirm", default=False): bool}
            ),
        )
