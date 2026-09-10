"""QR onboarding and on-demand Tuya account provisioning for LocalTuya."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
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
from homeassistant.helpers.selector import (
    QrCodeSelector,
    QrCodeSelectorConfig,
    QrErrorCorrectionLevel,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
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
from .zero_config import (
    ZeroConfigDecision,
    evaluate_prepared_zero_config,
)

_LOGGER = logging.getLogger(__name__)

CONF_QR_AUTH = "qr_auth"
CONF_QR_USER_CODE = "user_code"
CONF_QR_TERMINAL_ID = "terminal_id"
CONF_QR_ENDPOINT = "endpoint"
CONF_QR_TOKEN_INFO = "token_info"
CONF_IMPORT_JSON = "import_json"
CONF_IMPORT_DEVICE_ID = "import_device_id"
CONF_QR_BULK_DEVICE_IDS = "qr_bulk_device_ids"
CONF_QR_BULK_MODE = "qr_bulk_mode"
CONF_QR_GATEWAY_ID = "qr_gateway_id"

TUYA_CLIENT_ID = "HA_3y9q4ak7g4ephrvke"
TUYA_SCHEMA = "haauthorize"

# Tuya hub categories mirrored from the proven tuya-local onboarding model.
# These are transport/infrastructure devices, not entity platform guesses.
TUYA_HUB_CATEGORIES = frozenset(
    {
        "wgsxj",
        "lyqwg",
        "bywg",
        "zigbee",
        "wg2",
        "dgnzk",
        "videohub",
        "xnwg",
        "qtyycp",
        "alexa_yywg",
        "gywg",
        "cnwg",
        "wnykq",
        "wfcon",
    }
)

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


def _is_subdevice_flag(value: Any) -> bool:
    """Normalize Tuya SDK/export sub-device flags without string truthiness."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


def _first_device_attr(device: Any, *names: str) -> Any:
    """Return the first non-empty SDK attribute across known Tuya aliases."""
    for name in names:
        value = getattr(device, name, None)
        if value is not None and str(value).strip():
            return value
    return ""


def _assign_gateway_route(
    device: dict[str, Any],
    gateway_id: str,
    gateway: dict[str, Any],
) -> bool:
    """Attach one child to a selected/known gateway transport."""
    gateway_id = str(gateway_id or "").strip()
    if not gateway_id or not isinstance(gateway, dict):
        return False
    child_key = str(device.get(CONF_LOCAL_KEY) or "").strip()
    gateway_key = str(gateway.get(CONF_LOCAL_KEY) or "").strip()
    route_key = child_key or gateway_key
    device["gateway_id"] = gateway_id
    device["gateway_local_key"] = route_key
    device["gateway_ip"] = str(gateway.get("ip") or "").strip()
    device["gateway_name"] = gateway.get(CONF_NAME) or gateway_id
    device.pop("gateway_candidates", None)
    return bool(route_key)


def _enrich_gateway_routes(
    devices: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Resolve child routes conservatively while keeping children visible."""
    hubs = {
        str(device_id): device
        for device_id, device in devices.items()
        if isinstance(device, dict) and device.get("is_hub")
    }
    for device in devices.values():
        if not isinstance(device, dict) or not device.get("node_id"):
            continue
        gateway_id = str(device.get("gateway_id") or "").strip()
        gateway = devices.get(gateway_id) if gateway_id else None
        if isinstance(gateway, dict):
            _assign_gateway_route(device, gateway_id, gateway)
        elif len(hubs) == 1:
            inferred_id, inferred_gateway = next(iter(hubs.items()))
            _assign_gateway_route(device, inferred_id, inferred_gateway)
        elif hubs:
            device["gateway_candidates"] = sorted(hubs)
    return devices


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
    def user_code(self) -> str | None:
        """Return the User Code associated with this QR session."""
        return self._user_code

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
            self.last_error = {
                "msg": "User Code is required",
                "code": "missing_user_code",
            }
            return None

        response = await self.hass.async_add_executor_job(
            self._login_control.qr_code,
            TUYA_CLIENT_ID,
            TUYA_SCHEMA,
            user_code,
        )

        if not isinstance(response, dict) or not response.get("success", False):
            self.last_error = {
                "msg": str(
                    (response or {}).get(
                        "msg",
                        "Unable to generate QR code",
                    )
                ),
                "code": str((response or {}).get("code", "qr_failed")),
            }
            return None

        result = response.get("result")
        token = result.get("qrcode") if isinstance(result, dict) else None
        if not isinstance(token, str) or not token:
            self.last_error = {
                "msg": "Tuya returned an empty QR token",
                "code": "qr_failed",
            }
            return None

        self._user_code = user_code
        self._qr_token = token
        self.last_error = {}
        return token

    async def async_login(self) -> bool:
        """Exchange the scanned QR token for a renewable sharing session."""
        if not self._user_code or not self._qr_token:
            self.last_error = {
                "msg": "Generate and scan the QR code first",
                "code": "qr_missing",
            }
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
            raise QrProvisioningError(
                "qr_reauth_required",
                "Tuya account authorization is incomplete",
            )

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
            reason = (
                "qr_reauth_required"
                if "sign invalid" in message.lower()
                else "qr_cloud_unavailable"
            )
            raise QrProvisioningError(reason, message) from exc

        self._manager = manager
        devices: dict[str, dict[str, Any]] = {}

        for device in manager.device_map.values():
            device_id = str(getattr(device, "id", "") or "").strip()
            if not device_id:
                continue

            has_local_key_attr = hasattr(device, "local_key")
            local_key = str(getattr(device, "local_key", "") or "").strip()
            product_id = str(getattr(device, "product_id", "") or "").strip()
            category = str(getattr(device, "category", "") or "").strip()
            device_ip = str(getattr(device, "ip", "") or "").strip()
            is_subdevice = _is_subdevice_flag(
                _first_device_attr(device, "sub", "is_subdevice", "isSubDevice")
            )
            node_id = str(
                _first_device_attr(
                    device, "node_id", "nodeId", "cid", "device_cid", "deviceCid"
                )
                or ""
            ).strip()
            gateway_id = str(
                _first_device_attr(
                    device,
                    "gateway_id", "gatewayId",
                    "parent_id", "parentId",
                    "parent_dev_id", "parentDevId",
                    "parent_device_id", "parentDeviceId",
                    "hub_id", "hubId",
                )
                or ""
            ).strip()
            device_uuid = str(getattr(device, "uuid", "") or "").strip()
            if not node_id and device_uuid and (is_subdevice or not device_ip):
                node_id = device_uuid

            raw_fields = getattr(device, "__dict__", {})
            if isinstance(raw_fields, dict):
                _LOGGER.debug(
                    "Tuya sharing metadata category=%s fields=%s",
                    category or "unknown",
                    sorted(str(key) for key in raw_fields),
                )

            devices[device_id] = {
                "id": device_id,
                CONF_NAME: str(getattr(device, "name", "") or "").strip(),
                CONF_LOCAL_KEY: local_key,
                "product_id": product_id,
                "product_name": str(
                    getattr(device, "product_name", "") or ""
                ).strip(),
                "category": category,
                "online": bool(getattr(device, "online", False)),
                "support_local": bool(getattr(device, "support_local", False)),
                "sub": is_subdevice,
                "uuid": device_uuid,
                "node_id": node_id,
                "gateway_id": gateway_id,
                "is_hub": (
                    category in TUYA_HUB_CATEGORIES
                    or not has_local_key_attr
                ),
                "ip": device_ip,
            }

        return _enrich_gateway_routes(devices)

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
            _LOGGER.debug(
                "QR datamodel request failed for %s: %s",
                device_id,
                exc,
            )
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
        found_id = (
            candidate.get("gwId")
            or candidate.get("id")
            or candidate.get("devId")
            or candidate.get("deviceId")
            or candidate.get("dev_id")
        )
        if found_id == device_id:
            return copy.deepcopy(candidate)
    return None


async def _async_find_lan_device(
    hass,
    device_id: str,
) -> dict[str, Any] | None:
    """Find a specific Tuya device on LAN without trusting its cloud IP.

    tuya-local deliberately scans for the real LAN address instead of using the
    IP returned by Device Sharing.  Do the same here, with a few active 6699
    discovery requests before a bounded one-shot listener fallback.
    """
    domain_data = hass.data.get(DOMAIN, {})
    discovery = domain_data.get(DATA_DISCOVERY)

    if discovery is not None:
        for _attempt in range(3):
            try:
                await discovery.async_request_discovery()
            except Exception as exc:
                _LOGGER.debug("Targeted Tuya LAN discovery request failed: %s", exc)
            await asyncio.sleep(1.25)
            devices = getattr(discovery, "devices", {})
            if isinstance(devices, dict):
                found = _find_discovered_device(devices, device_id)
                if found is not None:
                    return found

    from .discovery import find_device

    try:
        # Match the proven TinyTuya/tuya-local find_device(dev_id=...) model:
        # listen on 6666/6667/7000, periodically rebroadcast REQ_DEVINFO for
        # slow 3.5 devices, and stop as soon as the requested ID appears.
        found = await find_device(device_id, hass=hass)
    except Exception as exc:
        _LOGGER.debug("Targeted Tuya LAN discovery fallback failed: %s", exc)
        return None

    return copy.deepcopy(found) if isinstance(found, dict) else None


def _qr_host_schema(default: str = "") -> vol.Schema:
    """Build the manual LAN-address fallback schema."""
    if default:
        marker = vol.Required(CONF_HOST, default=default)
    else:
        marker = vol.Required(CONF_HOST)
    return vol.Schema({marker: cv.string})


def _qr_is_locally_eligible(device: dict[str, Any]) -> bool:
    """Keep routable children visible even when their hub is ambiguous."""
    if not isinstance(device, dict):
        return False
    local_key = str(device.get(CONF_LOCAL_KEY) or "").strip()
    gateway_key = str(device.get("gateway_local_key") or "").strip()
    if str(device.get("node_id") or "").strip():
        return bool(local_key or gateway_key)
    return bool(local_key)


def _qr_needs_host_fallback(reason: str) -> bool:
    """Return whether an automatic LAN failure should ask for an address."""
    return reason in {
        "qr_device_host_required",
        "cannot_connect",
    }


async def async_prepare_qr_device(
    hass,
    cloud: QrCloudClient,
    cloud_device: dict[str, Any],
    *,
    host_override: str | None = None,
) -> tuple[dict[str, Any], list[Any]]:
    """Resolve identity, verify LAN access, detect protocol and map entities.

    Automatic Tuya discovery is preferred. When it cannot determine a usable
    address, callers can retry with ``host_override``. The override is never
    trusted by itself: Device ID/local_key authentication, protocol probing and
    datapoint retrieval must all succeed before the device can be stored.
    """
    device_id = str(cloud_device.get("id") or "").strip()
    node_id = str(cloud_device.get("node_id") or "").strip()
    gateway_id = str(cloud_device.get("gateway_id") or "").strip()
    local_key = str(
        (cloud_device.get("gateway_local_key") if node_id else None)
        or cloud_device.get(CONF_LOCAL_KEY)
        or ""
    ).strip()

    if not device_id or not local_key:
        raise QrProvisioningError(
            "qr_device_not_local",
            "Device ID/local_key is not available",
        )
    if node_id and not gateway_id:
        raise QrProvisioningError(
            "qr_subdevice_gateway_missing",
            "Tuya returned a child device without its parent gateway ID",
        )

    discovered: dict[str, Any] = {}

    if host_override is None:
        discovery_id = gateway_id if node_id else device_id
        found = await _async_find_lan_device(hass, discovery_id)
        if isinstance(found, dict):
            discovered = found

        # Device Sharing may expose a WAN/cached IP.  Never accept that field as
        # proof of the local endpoint: only LAN discovery or a user-supplied
        # address that subsequently passes the full protocol probe is trusted.
        host = str(discovered.get("ip") or "").strip()
        if not host:
            raise QrProvisioningError(
                "qr_device_host_required",
                "Automatic LAN discovery could not determine the device address",
            )
    else:
        host = str(host_override or "").strip()
        if not host:
            raise QrProvisioningError(
                "qr_device_host_required",
                "Enter the current device IP address or hostname",
            )
        discovered = {
            "gwId": gateway_id or device_id,
            "ip": host,
        }

    from .config_flow import (
        CannotConnect,
        EmptyDpsList,
        InvalidAuth,
        PROTOCOL_AUTO,
        validate_input,
    )

    device_data: dict[str, Any] = {
        CONF_FRIENDLY_NAME: (
            cloud_device.get(CONF_NAME)
            or cloud_device.get("product_name")
            or device_id
        ),
        CONF_HOST: host,
        CONF_DEVICE_ID: device_id,
        CONF_LOCAL_KEY: local_key,
        CONF_PROTOCOL_VERSION: PROTOCOL_AUTO,
        CONF_ENABLE_DEBUG: False,
        "product_id": cloud_device.get("product_id") or "",
    }
    if node_id:
        device_data["node_id"] = node_id
        device_data["gateway_id"] = gateway_id

    product_key = discovered.get("productKey") or cloud_device.get("product_id")
    if product_key:
        device_data[CONF_PRODUCT_KEY] = str(product_key)

    try:
        dps_strings, resolved_protocol = await validate_input(hass, device_data)
    except CannotConnect as exc:
        raise QrProvisioningError(
            "cannot_connect",
            "The device did not answer at the selected LAN address",
        ) from exc
    except InvalidAuth as exc:
        raise QrProvisioningError(
            "invalid_auth",
            "The device rejected the Device ID/local key returned by Tuya",
        ) from exc
    except EmptyDpsList as exc:
        raise QrProvisioningError(
            "empty_dps",
            "The LAN connection succeeded but the device returned no datapoints",
        ) from exc
    except Exception as exc:
        # Do not include exception text: lower-level libraries may include
        # credentials in exceptions. The class is enough for diagnostics.
        _LOGGER.error(
            "Unexpected QR LAN validation failure (%s)",
            type(exc).__name__,
        )
        raise QrProvisioningError(
            "unknown",
            "Unexpected error while validating the device over LAN",
        ) from exc

    device_data[CONF_PROTOCOL_VERSION] = resolved_protocol
    device_data[CONF_DPS_STRINGS] = list(dps_strings)

    # Cloud metadata is enrichment only and is fetched after LAN validation.
    # This keeps the save decision authoritative to the actual local device.
    model = await cloud.async_get_datamodel(device_id)
    merged_discovery = {
        **discovered,
        **cloud_device,
        "mapping": _datamodel_mapping(model),
    }
    merged_discovery["ip"] = host
    merged_discovery["gwId"] = device_id

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


def _normalize_import_device(
    raw: dict[str, Any],
    device_id_hint: str | None = None,
) -> dict[str, Any]:
    """Normalize supported LocalTuya/Tuya/TinyTuya device export shapes."""
    if not isinstance(raw, dict):
        raise ValueError("device must be an object")
    device_id = str(
        raw.get(CONF_DEVICE_ID)
        or raw.get("id")
        or raw.get("dev_id")
        or device_id_hint
        or ""
    ).strip()
    local_key = str(
        raw.get(CONF_LOCAL_KEY)
        or raw.get("localKey")
        or raw.get("key")
        or ""
    ).strip()
    if not device_id or not local_key:
        raise QrProvisioningError(
            "import_missing_credentials",
            "Device ID and local_key are required",
        )
    host = str(raw.get(CONF_HOST) or raw.get("ip") or "").strip()
    name = str(
        raw.get(CONF_FRIENDLY_NAME)
        or raw.get(CONF_NAME)
        or raw.get("product_name")
        or device_id
    ).strip()
    protocol = str(
        raw.get(CONF_PROTOCOL_VERSION)
        or raw.get("version")
        or raw.get("protocol")
        or "auto"
    ).strip()
    if protocol not in {"auto", "3.1", "3.2", "3.3", "3.4", "3.5"}:
        protocol = "auto"
    gateway_id = str(
        raw.get("gateway_id")
        or raw.get("gatewayId")
        or raw.get("parent_id")
        or ""
    ).strip()
    node_id = str(
        raw.get("node_id")
        or raw.get("cid")
        or raw.get("device_cid")
        or ""
    ).strip()
    if not node_id and _is_subdevice_flag(raw.get("sub", False)) and gateway_id:
        node_id = str(raw.get("uuid") or "").strip()
    result: dict[str, Any] = {
        CONF_FRIENDLY_NAME: name or device_id,
        CONF_HOST: host,
        CONF_DEVICE_ID: device_id,
        CONF_LOCAL_KEY: local_key,
        CONF_PROTOCOL_VERSION: protocol,
        CONF_ENABLE_DEBUG: bool(raw.get(CONF_ENABLE_DEBUG, False)),
    }
    if node_id:
        result["node_id"] = node_id
    if gateway_id:
        result["gateway_id"] = gateway_id
    product_key = (
        raw.get(CONF_PRODUCT_KEY)
        or raw.get("productKey")
        or raw.get("product_id")
        or raw.get("productId")
    )
    if product_key:
        result[CONF_PRODUCT_KEY] = str(product_key)
    product_id = raw.get("product_id") or raw.get("productId")
    if product_id:
        result["product_id"] = str(product_id)
    for key in ("scan_interval", "manual_dps", "reset_dpids", "model"):
        if key in raw and raw[key] is not None:
            result[key] = copy.deepcopy(raw[key])
    entities = raw.get(CONF_ENTITIES)
    if isinstance(entities, list):
        result[CONF_ENTITIES] = [
            copy.deepcopy(entity)
            for entity in entities
            if isinstance(entity, dict)
        ]
    return result


def _parse_import_payload(value: str) -> dict[str, dict[str, Any]]:
    """Parse one device, a device list, or a LocalTuya root devices object."""
    try:
        payload = json.loads(str(value or ""))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON") from exc
    records: dict[str, dict[str, Any]] = {}

    def add(raw: Any, hint: str | None = None) -> None:
        if not isinstance(raw, dict):
            return
        device = _normalize_import_device(raw, hint)
        records[device[CONF_DEVICE_ID]] = device

    if isinstance(payload, dict) and isinstance(payload.get(CONF_DEVICES), dict):
        for device_id, raw in payload[CONF_DEVICES].items():
            add(raw, str(device_id))
    elif isinstance(payload, list):
        for raw in payload:
            add(raw)
    elif isinstance(payload, dict):
        add(payload)
    else:
        raise ValueError("unsupported JSON root")
    if not records:
        raise ValueError("no devices found")
    return records


class QrConfigFlowMixin:
    """Config-flow steps for recommended QR onboarding and manual fallback."""

    def _import_schema(self):
        source = getattr(self, "_import_source", "")
        return vol.Schema(
            {
                vol.Required(
                    CONF_IMPORT_JSON,
                    default=source,
                ): TextSelector(
                    TextSelectorConfig(multiline=True)
                )
            }
        )

    async def async_step_import_existing(self, user_input=None):
        """Import existing Device ID/local_key configuration without Tuya login."""
        errors = {}
        placeholders = {}
        if user_input is not None:
            self._import_source = str(user_input.get(CONF_IMPORT_JSON, ""))
            try:
                self._import_devices = _parse_import_payload(self._import_source)
            except QrProvisioningError as exc:
                errors["base"] = exc.reason
                placeholders = {"msg": exc.detail}
            except ValueError:
                errors["base"] = "import_invalid"
            else:
                if len(self._import_devices) == 1:
                    return await self._async_start_import_device(
                        next(iter(self._import_devices.values()))
                    )
                return await self.async_step_import_choose_device()
        return self.async_show_form(
            step_id="import_existing",
            data_schema=self._import_schema(),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_import_choose_device(self, user_input=None):
        devices = getattr(self, "_import_devices", {})
        if not devices:
            return await self.async_step_import_existing()
        labels = {
            device_id: (
                f"{device.get(CONF_FRIENDLY_NAME) or device_id} "
                f"({device.get(CONF_HOST) or 'LAN discovery'})"
            )
            for device_id, device in devices.items()
        }
        if user_input is not None:
            return await self._async_start_import_device(
                devices[user_input[CONF_IMPORT_DEVICE_ID]]
            )
        return self.async_show_form(
            step_id="import_choose_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IMPORT_DEVICE_ID): vol.In(labels)
                }
            ),
        )

    async def _async_start_import_device(self, imported: dict[str, Any]):
        from .config_flow import (
            CannotConnect,
            EmptyDpsList,
            InvalidAuth,
            async_get_entity_candidates,
            validate_input,
        )

        device_data = copy.deepcopy(imported)
        device_id = device_data[CONF_DEVICE_ID]
        try:
            discovery = {}
            if not device_data.get(CONF_HOST):
                discovery = await _async_discovery_snapshot(self.hass)
                discovered = _find_discovered_device(discovery, device_id)
                if discovered is None or not discovered.get("ip"):
                    raise QrProvisioningError(
                        "import_device_not_on_lan",
                        "The imported device was not found on the Home Assistant LAN",
                    )
                device_data[CONF_HOST] = discovered["ip"]
            dps_strings, resolved = await validate_input(self.hass, device_data)
            device_data[CONF_PROTOCOL_VERSION] = resolved
            device_data[CONF_DPS_STRINGS] = list(dps_strings)
            existing_entities = device_data.get(CONF_ENTITIES)
            self._manual_device_data = device_data
            self._manual_dps_strings = list(dps_strings)
            self._manual_entities = (
                copy.deepcopy(existing_entities)
                if isinstance(existing_entities, list)
                else []
            )
            if self._manual_entities:
                return self._finish_manual_initial_device()
            if not discovery:
                try:
                    discovery = await _async_discovery_snapshot(self.hass)
                except QrProvisioningError:
                    discovery = {}
            self._manual_candidates = list(
                await async_get_entity_candidates(
                    self.hass,
                    device_data,
                    discovery,
                    dps_strings,
                )
            )
            if self._manual_candidates:
                return await self.async_step_manual_mapping_review()
            return await self.async_step_manual_pick_entity_type()
        except CannotConnect:
            error, placeholders = "cannot_connect", {}
        except InvalidAuth:
            error, placeholders = "invalid_auth", {}
        except EmptyDpsList:
            error, placeholders = "empty_dps", {}
        except QrProvisioningError as exc:
            error, placeholders = exc.reason, {"msg": exc.detail}
        except Exception as exc:
            _LOGGER.error(
                "Unexpected imported-device validation failure (%s)",
                type(exc).__name__,
            )
            error, placeholders = "unknown", {}
        return self.async_show_form(
            step_id="import_existing",
            data_schema=self._import_schema(),
            errors={"base": error},
            description_placeholders=placeholders,
        )

    async def async_step_qr_login(self, user_input=None):
        """Collect the Smart Life/Tuya User Code and generate a QR token."""
        errors = {}
        placeholders = {}
        if user_input is not None:
            self._qr_cloud = QrCloudClient(self.hass)
            token = await self._qr_cloud.async_generate_qr(
                user_input[CONF_QR_USER_CODE]
            )
            if token:
                self._qr_token = token
                return await self.async_step_qr_scan()
            errors["base"] = "qr_login_error"
            placeholders = self._qr_cloud.last_error

        return self.async_show_form(
            step_id="qr_login",
            data_schema=vol.Schema(
                {vol.Required(CONF_QR_USER_CODE): str}
            ),
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
                                error_correction_level=(
                                    QrErrorCorrectionLevel.QUARTILE
                                ),
                            )
                        )
                    }
                ),
            )

        if not await cloud.async_login():
            refreshed = await cloud.async_generate_qr(cloud.user_code)
            if refreshed:
                self._qr_token = refreshed
            return self.async_show_form(
                step_id="qr_scan",
                data_schema=vol.Schema(
                    {
                        vol.Optional("QR"): QrCodeSelector(
                            config=QrCodeSelectorConfig(
                                data=(
                                    "tuyaSmart--qrLogin?token="
                                    f"{self._qr_token}"
                                ),
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
            if _qr_is_locally_eligible(device)
        }
        if not eligible:
            return self.async_abort(reason="qr_no_local_devices")

        if user_input is not None:
            selected = user_input[CONF_DEVICE_ID]
            cloud_device = copy.deepcopy(eligible[selected])
            if cloud_device.get("node_id") and not cloud_device.get("gateway_id"):
                gateway_id = str(user_input.get(CONF_QR_GATEWAY_ID) or "").strip()
                gateway = devices.get(gateway_id) if gateway_id else None
                if not isinstance(gateway, dict) or not gateway.get("is_hub"):
                    return self.async_show_form(
                        step_id="qr_choose_device",
                        data_schema=self._qr_device_schema(eligible, devices),
                        errors={"base": "qr_subdevice_gateway_missing"},
                        description_placeholders={
                            "msg": "Select the hub/gateway used by this sub-device"
                        },
                    )
                _assign_gateway_route(cloud_device, gateway_id, gateway)
            self._qr_selected_device = copy.deepcopy(cloud_device)
            try:
                (
                    self._qr_device_data,
                    self._qr_medium_candidates,
                ) = await async_prepare_qr_device(
                    self.hass,
                    self._qr_cloud,
                    cloud_device,
                )
            except QrProvisioningError as exc:
                if _qr_needs_host_fallback(exc.reason):
                    self._qr_manual_host = ""
                    return await self.async_step_qr_device_host()
                return self.async_show_form(
                    step_id="qr_choose_device",
                    data_schema=self._qr_device_schema(eligible, devices),
                    errors={"base": exc.reason},
                    description_placeholders={"msg": exc.detail},
                )

            decision = evaluate_prepared_zero_config(
                self._qr_device_data,
                self._qr_medium_candidates,
            )
            if decision.decision is ZeroConfigDecision.REVIEW_REQUIRED:
                return await self.async_step_qr_mapping_review()
            if decision.decision is not ZeroConfigDecision.AUTO_CONFIGURE:
                return self.async_abort(reason="qr_mapping_not_found")
            self._qr_device_data[CONF_ENTITIES] = copy.deepcopy(decision.entities)
            return await self._async_finish_initial_qr()

        return self.async_show_form(
            step_id="qr_choose_device",
            data_schema=self._qr_device_schema(eligible, devices),
        )

    async def async_step_qr_device_host(self, user_input=None):
        """Fallback to a user-supplied LAN address and validate it end-to-end."""
        cloud_device = getattr(self, "_qr_selected_device", None)
        cloud = getattr(self, "_qr_cloud", None)
        if not isinstance(cloud_device, dict) or cloud is None:
            return await self.async_step_qr_choose_device()

        errors = {}
        placeholders = {}
        if user_input is not None:
            host = str(user_input.get(CONF_HOST, "") or "").strip()
            self._qr_manual_host = host
            if not host:
                errors["base"] = "qr_device_host_required"
                placeholders = {
                    "msg": "Enter the current device IP address or hostname"
                }
            else:
                try:
                    (
                        self._qr_device_data,
                        self._qr_medium_candidates,
                    ) = await async_prepare_qr_device(
                        self.hass,
                        cloud,
                        cloud_device,
                        host_override=host,
                    )
                except QrProvisioningError as exc:
                    errors["base"] = exc.reason
                    placeholders = {"msg": exc.detail}
                else:
                    decision = evaluate_prepared_zero_config(
                        self._qr_device_data,
                        self._qr_medium_candidates,
                    )
                    if decision.decision is ZeroConfigDecision.REVIEW_REQUIRED:
                        return await self.async_step_qr_mapping_review()
                    if decision.decision is not ZeroConfigDecision.AUTO_CONFIGURE:
                        return self.async_abort(reason="qr_mapping_not_found")
                    self._qr_device_data[CONF_ENTITIES] = copy.deepcopy(decision.entities)
                    return await self._async_finish_initial_qr()

        return self.async_show_form(
            step_id="qr_device_host",
            data_schema=_qr_host_schema(
                getattr(self, "_qr_manual_host", "")
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    @staticmethod
    def _qr_device_schema(
        devices: dict[str, dict[str, Any]],
        all_devices: dict[str, dict[str, Any]] | None = None,
    ):
        labels = {
            device_id: (
                f"{device.get(CONF_NAME) or device_id}"
                f" ({device.get('product_name') or device.get('category') or 'Tuya'})"
            )
            for device_id, device in devices.items()
        }
        schema: dict[Any, Any] = {
            vol.Required(CONF_DEVICE_ID): vol.In(labels)
        }
        hubs = {
            str(device_id): (
                f"{device.get(CONF_NAME) or device_id}"
                f" ({device.get('product_name') or device.get('category') or 'Gateway'})"
            )
            for device_id, device in (all_devices or devices).items()
            if isinstance(device, dict) and device.get("is_hub")
        }
        if hubs:
            schema[vol.Optional(CONF_QR_GATEWAY_ID, default="")] = vol.In(
                {"": "Automatic / none", **hubs}
            )
        return vol.Schema(schema)

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
                device_data[CONF_ENTITIES].append(
                    copy.deepcopy(candidate.config)
                )
            if not device_data[CONF_ENTITIES]:
                return self.async_show_form(
                    step_id="qr_mapping_review",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                "qr_mapping_selection",
                                default=list(options),
                            ): cv.multi_select(options)
                        }
                    ),
                    errors={"base": "qr_mapping_required"},
                )
            return await self._async_finish_initial_qr()

        return self.async_show_form(
            step_id="qr_mapping_review",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "qr_mapping_selection",
                        default=list(options),
                    ): cv.multi_select(options)
                }
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
        from .config_flow import (
            DEVICE_SCHEMA,
            CannotConnect,
            EmptyDpsList,
            InvalidAuth,
            async_get_entity_candidates,
            schema_defaults,
            validate_input,
        )

        errors = {}
        if user_input is not None:
            try:
                dps_strings, resolved = await validate_input(
                    self.hass,
                    user_input,
                )
                device_data = dict(user_input)
                device_data[CONF_PROTOCOL_VERSION] = resolved
                device_data[CONF_DPS_STRINGS] = list(dps_strings)

                try:
                    discovery = await _async_discovery_snapshot(self.hass)
                except QrProvisioningError:
                    discovery = {}

                candidates = await async_get_entity_candidates(
                    self.hass,
                    device_data,
                    discovery,
                    dps_strings,
                )

                self._manual_device_data = device_data
                self._manual_dps_strings = list(dps_strings)
                self._manual_entities = []
                self._manual_candidates = list(candidates)

                if self._manual_candidates:
                    return await self.async_step_manual_mapping_review()

                return await self.async_step_manual_pick_entity_type()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except EmptyDpsList:
                errors["base"] = "empty_dps"
            except Exception as exc:
                _LOGGER.exception(
                    "Unexpected manual onboarding failure: %s",
                    exc,
                )
                errors["base"] = "unknown"

        defaults = {
            CONF_PROTOCOL_VERSION: "auto",
            CONF_ENABLE_DEBUG: False,
        }
        return self.async_show_form(
            step_id="manual_device",
            data_schema=schema_defaults(DEVICE_SCHEMA, **defaults),
            errors=errors,
        )

    async def async_step_manual_mapping_review(self, user_input=None):
        """Offer automatic Catalog/mapper suggestions before manual DP setup."""
        candidates = getattr(self, "_manual_candidates", [])
        if not candidates:
            return await self.async_step_manual_pick_entity_type()

        options = _candidate_options(candidates)
        default_selection = [
            str(index)
            for index, candidate in enumerate(candidates)
            if candidate.confidence == MappingConfidence.HIGH
        ]

        if user_input is not None:
            selected = set(
                user_input.get("manual_mapping_selection", [])
            )
            self._manual_entities = [
                copy.deepcopy(candidate.config)
                for index, candidate in enumerate(candidates)
                if str(index) in selected
            ]
            return await self.async_step_manual_pick_entity_type()

        return self.async_show_form(
            step_id="manual_mapping_review",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "manual_mapping_selection",
                        default=default_selection,
                    ): cv.multi_select(options)
                }
            ),
        )

    def _manual_available_dps(self) -> list[str]:
        """Return primary DPS not already used by a manual/automatic entity."""
        used = {
            str(entity.get("id"))
            for entity in getattr(self, "_manual_entities", [])
            if entity.get("id") is not None
        }
        return [
            value
            for value in getattr(self, "_manual_dps_strings", [])
            if str(value).split(" ", 1)[0] not in used
        ]

    async def async_step_manual_pick_entity_type(self, user_input=None):
        """Allow advanced users to add entities even without a Catalog match."""
        from .const import PLATFORMS

        entities = getattr(self, "_manual_entities", [])
        available = self._manual_available_dps()

        if user_input is not None:
            if user_input.get("manual_finish", False):
                if entities:
                    return self._finish_manual_initial_device()
            else:
                self._manual_platform = user_input["manual_platform"]
                return await self.async_step_manual_configure_entity()

        if not available and entities:
            return self._finish_manual_initial_device()

        schema = {
            vol.Required(
                "manual_platform",
                default="switch",
            ): vol.In(PLATFORMS)
        }
        if entities:
            schema[vol.Required("manual_finish", default=True)] = bool

        return self.async_show_form(
            step_id="manual_pick_entity_type",
            data_schema=vol.Schema(schema),
        )

    async def async_step_manual_configure_entity(self, user_input=None):
        """Configure one entity using the normal LocalTuya platform schema."""
        from homeassistant.const import CONF_PLATFORM
        from .config_flow import (
            platform_schema,
            schema_defaults,
            strip_dps_values,
        )

        available = self._manual_available_dps()
        if not available:
            return await self.async_step_manual_pick_entity_type()

        platform = self._manual_platform
        schema = await platform_schema(
            self.hass,
            platform,
            available,
        )

        if user_input is not None:
            entity = strip_dps_values(
                user_input,
                available,
            )
            entity[CONF_PLATFORM] = platform
            self._manual_entities.append(entity)
            return await self.async_step_manual_pick_entity_type()

        return self.async_show_form(
            step_id="manual_configure_entity",
            data_schema=schema_defaults(
                schema,
                available,
            ),
            description_placeholders={
                "entity": "an entity",
                "platform": platform,
            },
        )

    def _finish_manual_initial_device(self):
        """Persist a fully manual first device in the local-only root entry."""
        device_data = copy.deepcopy(self._manual_device_data)
        device_data[CONF_ENTITIES] = copy.deepcopy(self._manual_entities)
        data = _base_entry_data()
        data[CONF_DEVICES][device_data[CONF_DEVICE_ID]] = device_data
        return self.async_create_entry(title=DOMAIN, data=data)


class QrOptionsFlowMixin:
    """Options-flow steps for future device sync without repeating QR login."""

    async def _async_load_linked_qr_devices(self):
        """Refresh linked devices once and persist any refreshed QR token."""
        if getattr(self, "_qr_devices", None) and getattr(self, "_qr_cloud", None):
            return None
        auth = self.config_entry.data.get(CONF_QR_AUTH)
        if not isinstance(auth, dict) or not auth:
            return "qr_not_linked"
        self._qr_cloud = QrCloudClient(self.hass, auth)
        try:
            self._qr_devices = await self._qr_cloud.async_get_devices()
        except QrProvisioningError as exc:
            return exc.reason
        self._persist_qr_auth(self._qr_cloud.auth)
        return None

    def _bulk_eligible_devices(self):
        """Return linked devices not already configured in this entry."""
        devices = getattr(self, "_qr_devices", {})
        configured = set(self.config_entry.data.get(CONF_DEVICES, {}))
        return {
            str(device_id): device
            for device_id, device in devices.items()
            if str(device_id) not in configured
        }

    async def _async_bulk_prepare_devices(self, device_ids):
        """Provision selected devices sequentially while isolating failures."""
        devices = getattr(self, "_qr_devices", {})
        cloud = getattr(self, "_qr_cloud", None)
        successes = []
        failures = []
        for raw_device_id in device_ids:
            device_id = str(raw_device_id)
            cloud_device = devices.get(device_id)
            if not isinstance(cloud_device, dict):
                failures.append({"device_id": device_id, "reason": "device_not_found"})
                continue
            try:
                device_data, candidates = await async_prepare_qr_device(
                    self.hass,
                    cloud,
                    cloud_device,
                )
            except QrProvisioningError as exc:
                failures.append({"device_id": device_id, "reason": exc.reason})
                continue
            except Exception as exc:  # noqa: BLE001 - isolate one device in bulk mode.
                _LOGGER.debug(
                    "Bulk QR provisioning failed for one device: %s",
                    type(exc).__name__,
                )
                failures.append({"device_id": device_id, "reason": "probe_error"})
                continue
            successes.append(
                {
                    "device_id": device_id,
                    "device_data": device_data,
                    "candidates": candidates,
                }
            )
        return {"successes": successes, "failures": failures}

    @staticmethod
    def _qr_bulk_schema(eligible):
        """Build the privacy-safe multi-select schema for linked devices."""
        options = [
            {
                "value": str(device_id),
                "label": str(device.get(CONF_NAME) or device_id),
            }
            for device_id, device in eligible.items()
        ]
        return vol.Schema(
            {
                vol.Required(CONF_QR_BULK_DEVICE_IDS): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

    async def async_step_qr_bulk_choose_devices(self, user_input=None):
        """Select multiple linked Tuya devices for sequential LAN onboarding."""
        load_error = await self._async_load_linked_qr_devices()
        if load_error:
            return self.async_abort(reason=load_error)
        eligible = self._bulk_eligible_devices()
        if not eligible:
            return self.async_abort(reason="qr_no_new_local_devices")
        if user_input is not None:
            selected = [
                str(device_id)
                for device_id in user_input.get(CONF_QR_BULK_DEVICE_IDS, [])
                if str(device_id) in eligible
            ]
            if not selected:
                return self.async_show_form(
                    step_id="qr_bulk_choose_devices",
                    data_schema=self._qr_bulk_schema(eligible),
                    errors={"base": "select_at_least_one_device"},
                )
            self._qr_bulk_result = await self._async_bulk_prepare_devices(selected)
            self._qr_bulk_summary = None
            return await self.async_step_qr_bulk_summary()
        return self.async_show_form(
            step_id="qr_bulk_choose_devices",
            data_schema=self._qr_bulk_schema(eligible),
        )

    async def async_step_qr_bulk_summary(self, user_input=None):
        """Persist deterministic devices only and show a count-only summary."""
        if getattr(self, "_qr_bulk_summary", None) is None:
            result = getattr(
                self,
                "_qr_bulk_result",
                {"successes": [], "failures": []},
            )
            successes = result.get("successes", [])
            failures = result.get("failures", [])
            entry_data = copy.deepcopy(dict(self.config_entry.data))
            devices = entry_data.setdefault(CONF_DEVICES, {})
            if not isinstance(devices, dict):
                devices = {}
                entry_data[CONF_DEVICES] = devices

            added = []
            review_required = []
            for item in successes:
                device_data = copy.deepcopy(item["device_data"])
                decision = evaluate_prepared_zero_config(
                    device_data,
                    item.get("candidates", []),
                )
                if decision.decision is not ZeroConfigDecision.AUTO_CONFIGURE:
                    review_required.append(str(item["device_id"]))
                    continue
                device_data[CONF_ENTITIES] = copy.deepcopy(decision.entities)
                devices[str(item["device_id"])] = device_data
                added.append(str(item["device_id"]))

            if added and hasattr(self.hass, "config_entries"):
                entry_data[ATTR_UPDATED_AT] = str(int(time.time() * 1000))
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=entry_data,
                )

            self._qr_bulk_summary = {
                "added": added,
                "review_required": review_required,
                "failures": failures,
            }

        summary = self._qr_bulk_summary
        if user_input is not None:
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="qr_bulk_summary",
            data_schema=vol.Schema({}),
            description_placeholders={
                "added_count": str(len(summary["added"])),
                "failed_count": str(len(summary["failures"])),
                "review_count": str(len(summary["review_required"])),
            },
        )

    async def async_step_add_device_method(self, user_input=None):
        """Choose linked-account provisioning or account-management actions."""
        return self.async_show_menu(
            step_id="add_device_method",
            menu_options=[
                "qr_add_device",
                "qr_bulk_choose_devices",
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
            and _qr_is_locally_eligible(device)
        }
        if not eligible:
            return self.async_abort(reason="qr_no_new_local_devices")

        if user_input is not None:
            selected = user_input[CONF_DEVICE_ID]
            cloud_device = eligible[selected]
            self._qr_selected_device = copy.deepcopy(cloud_device)
            try:
                (
                    self._qr_device_data,
                    self._qr_medium_candidates,
                ) = await async_prepare_qr_device(
                    self.hass,
                    self._qr_cloud,
                    cloud_device,
                )
            except QrProvisioningError as exc:
                if _qr_needs_host_fallback(exc.reason):
                    self._qr_manual_host = ""
                    return await self.async_step_qr_add_device_host()
                return self.async_show_form(
                    step_id="qr_add_device",
                    data_schema=QrConfigFlowMixin._qr_device_schema(eligible),
                    errors={"base": exc.reason},
                    description_placeholders={"msg": exc.detail},
                )

            decision = evaluate_prepared_zero_config(
                self._qr_device_data,
                self._qr_medium_candidates,
            )
            if decision.decision is ZeroConfigDecision.REVIEW_REQUIRED:
                return await self.async_step_qr_add_mapping_review()
            if decision.decision is not ZeroConfigDecision.AUTO_CONFIGURE:
                return self.async_abort(reason="qr_mapping_not_found")
            self._qr_device_data[CONF_ENTITIES] = copy.deepcopy(decision.entities)
            return self._finish_qr_added_device()

        return self.async_show_form(
            step_id="qr_add_device",
            data_schema=QrConfigFlowMixin._qr_device_schema(eligible),
        )

    async def async_step_qr_add_device_host(self, user_input=None):
        """Fallback to an explicit LAN address for a newly synced device."""
        cloud_device = getattr(self, "_qr_selected_device", None)
        cloud = getattr(self, "_qr_cloud", None)
        if not isinstance(cloud_device, dict) or cloud is None:
            return await self.async_step_qr_add_device()

        errors = {}
        placeholders = {}
        if user_input is not None:
            host = str(user_input.get(CONF_HOST, "") or "").strip()
            self._qr_manual_host = host
            if not host:
                errors["base"] = "qr_device_host_required"
                placeholders = {
                    "msg": "Enter the current device IP address or hostname"
                }
            else:
                try:
                    (
                        self._qr_device_data,
                        self._qr_medium_candidates,
                    ) = await async_prepare_qr_device(
                        self.hass,
                        cloud,
                        cloud_device,
                        host_override=host,
                    )
                except QrProvisioningError as exc:
                    errors["base"] = exc.reason
                    placeholders = {"msg": exc.detail}
                else:
                    decision = evaluate_prepared_zero_config(
                        self._qr_device_data,
                        self._qr_medium_candidates,
                    )
                    if decision.decision is ZeroConfigDecision.REVIEW_REQUIRED:
                        return await self.async_step_qr_add_mapping_review()
                    if decision.decision is not ZeroConfigDecision.AUTO_CONFIGURE:
                        return self.async_abort(reason="qr_mapping_not_found")
                    self._qr_device_data[CONF_ENTITIES] = copy.deepcopy(decision.entities)
                    return self._finish_qr_added_device()

        return self.async_show_form(
            step_id="qr_add_device_host",
            data_schema=_qr_host_schema(
                getattr(self, "_qr_manual_host", "")
            ),
            errors=errors,
            description_placeholders=placeholders,
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
                device_data[CONF_ENTITIES].append(
                    copy.deepcopy(candidate.config)
                )
            if not device_data[CONF_ENTITIES]:
                return self.async_show_form(
                    step_id="qr_add_mapping_review",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                "qr_mapping_selection",
                                default=list(options),
                            ): cv.multi_select(options)
                        }
                    ),
                    errors={"base": "qr_mapping_required"},
                )
            return self._finish_qr_added_device()

        return self.async_show_form(
            step_id="qr_add_mapping_review",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "qr_mapping_selection",
                        default=list(options),
                    ): cv.multi_select(options)
                }
            ),
        )

    def _finish_qr_added_device(self):
        """Persist a QR-provisioned device; its runtime is fully LAN-based."""
        new_data = copy.deepcopy(dict(self.config_entry.data))
        device_data = copy.deepcopy(self._qr_device_data)
        new_data.setdefault(CONF_DEVICES, {})[
            device_data[CONF_DEVICE_ID]
        ] = device_data
        new_data[CONF_QR_AUTH] = self._qr_cloud.auth
        new_data[ATTR_UPDATED_AT] = str(
            int(__import__("time").time() * 1000)
        )
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=new_data,
        )
        return self.async_create_entry(title="", data={})

    def _persist_qr_auth(self, auth: dict[str, Any]) -> None:
        """Persist QR authorization and migrate the entry to LAN-only runtime."""
        new_data = copy.deepcopy(dict(self.config_entry.data))
        new_data[CONF_QR_AUTH] = copy.deepcopy(auth)

        new_data[CONF_NO_CLOUD] = True
        new_data[CONF_CLIENT_ID] = ""
        new_data[CONF_CLIENT_SECRET] = ""
        new_data[CONF_USER_ID] = ""

        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=new_data,
        )

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
