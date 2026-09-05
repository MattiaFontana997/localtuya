"""Remote LocalTuya device mapping catalog."""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aiohttp import ClientError, ClientTimeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .advanced_mapping import (
    CONF_ADVANCED_MAPPING,
    advanced_mapping_dp_references,
    prune_advanced_mapping,
    validate_advanced_mapping,
)
from .const import CONF_EXTRA_STATE_ATTRIBUTES_DPS, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CATALOG_SCHEMA_VERSION = 3
SUPPORTED_CATALOG_SCHEMA_VERSIONS = {1, 2, 3}
CATALOG_URL = (
    "https://raw.githubusercontent.com/"
    "MattiaFontana997/localtuya-device-catalog/main/catalog.json"
)
REQUEST_TIMEOUT = ClientTimeout(total=10)
MAX_REMOTE_CATALOG_BYTES = 2 * 1024 * 1024
MAX_CATALOG_MAPPINGS = 4096
MAX_PRODUCT_IDS = 64
MAX_DP_ID = 65535
MAX_CONFIG_DEPTH = 12
MAX_CONFIG_NODES = 4096
BUILTIN_CATALOG_PATH = Path(__file__).with_name("builtin_catalog.json")
CATALOG_STORAGE_VERSION = 1
CATALOG_STORAGE_KEY = "localtuya.device_catalog"
SUPPORTED_PLATFORMS = frozenset(PLATFORMS)

_FORBIDDEN_CONFIG_KEYS = {
    "local_key", "device_id", "host", "ip", "gwid", "client_id",
    "client_secret", "user_id", "username", "region",
}
_PROTECTED_OVERRIDE_KEYS = {"id", "platform", "friendly_name"}
_DP_REFERENCE_KEYS = {
    "id", "brightness", "color_temp", "color_mode", "color", "scene",
    "effect", "current", "current_consumption", "voltage",
    "fan_speed_control", "fan_oscillating_control", "fan_direction",
}
_PROVENANCE_KEYS = {"source", "path", "revision", "license"}


@dataclass(frozen=True, slots=True)
class CatalogMatch:
    """A validated mapping returned by the device catalog."""

    mapping_id: str
    product_id: str
    confidence: str
    required_dps: tuple[int, ...]
    entities: tuple[dict[str, Any], ...]
    source: str = "remote"
    product_ids: tuple[str, ...] = ()
    optional_dps: tuple[int, ...] = ()
    provenance: dict[str, str] | None = None
    match_kind: str = "product"


def _device_product_id(device: dict[str, Any]) -> str | None:
    for key in ("product_id", "productId", "product_key", "productKey"):
        value = device.get(key)
        if value:
            return str(value).strip()
    return None


def _device_category(device: dict[str, Any]) -> str:
    value = device.get("category")
    return str(value).strip().lower() if value else ""


def _normalize_config_key(value: Any) -> str:
    return "".join(char for char in str(value).casefold() if char.isalnum())


_FORBIDDEN_CONFIG_KEY_TOKENS = {_normalize_config_key(key) for key in _FORBIDDEN_CONFIG_KEYS}
_PROTECTED_OVERRIDE_KEY_TOKENS = {_normalize_config_key(key) for key in _PROTECTED_OVERRIDE_KEYS}


def _json_structure_safe(value: Any) -> bool:
    stack = [(value, 0)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if depth > MAX_CONFIG_DEPTH or nodes > MAX_CONFIG_NODES:
            return False
        if isinstance(current, dict):
            for key, child in current.items():
                if not isinstance(key, str):
                    return False
                stack.append((child, depth + 1))
        elif isinstance(current, list):
            stack.extend((child, depth + 1) for child in current)
        elif not isinstance(current, (str, int, float, bool, type(None))):
            return False
    return True


def _contains_forbidden_keys(value: Any) -> bool:
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, child in current.items():
                if _normalize_config_key(key) in _FORBIDDEN_CONFIG_KEY_TOKENS:
                    return True
                stack.append(child)
        elif isinstance(current, list):
            stack.extend(current)
    return False


def _is_dp_reference_key(key: str) -> bool:
    return key in _DP_REFERENCE_KEYS or key.endswith("_dp")


def _config_dp_references(config: dict[str, Any]) -> set[int]:
    result: set[int] = set()
    extra = config.get(CONF_EXTRA_STATE_ATTRIBUTES_DPS)
    if isinstance(extra, dict):
        for value in extra.values():
            if isinstance(value, bool):
                continue
            try:
                dp_id = int(value)
            except (TypeError, ValueError):
                continue
            if 0 < dp_id <= MAX_DP_ID:
                result.add(dp_id)
    for key, value in config.items():
        if not _is_dp_reference_key(str(key)) or isinstance(value, bool):
            continue
        try:
            dp_id = int(value)
        except (TypeError, ValueError):
            continue
        if 0 < dp_id <= MAX_DP_ID:
            result.add(dp_id)
    result.update(advanced_mapping_dp_references(config.get(CONF_ADVANCED_MAPPING)))
    return result


def _normalize_dps(value: Any) -> list[int] | None:
    if not isinstance(value, list):
        return None
    result: list[int] = []
    for raw_dp in value:
        if isinstance(raw_dp, bool):
            return None
        try:
            dp_id = int(raw_dp)
        except (TypeError, ValueError):
            return None
        if dp_id <= 0 or dp_id > MAX_DP_ID:
            return None
        if dp_id not in result:
            result.append(dp_id)
    return sorted(result)


def _normalize_product_ids(value: Any, *, allow_empty: bool = False) -> list[str] | None:
    if not isinstance(value, list) or len(value) > MAX_PRODUCT_IDS or (not value and not allow_empty):
        return None
    result: list[str] = []
    for raw in value:
        if not isinstance(raw, str) or not raw.strip():
            return None
        product_id = raw.strip()
        if product_id not in result:
            result.append(product_id)
    return sorted(result)


def _validate_fingerprint(value: Any) -> dict[str, str] | None:
    """Validate deliberately small, non-heuristic fingerprint grammar."""
    if not isinstance(value, dict) or set(value) != {"mode"}:
        return None
    if value.get("mode") != "exact_dps":
        return None
    return {"mode": "exact_dps"}


def _validate_provenance(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not _json_structure_safe(value) or set(value) - _PROVENANCE_KEYS:
        return None
    source = value.get("source")
    license_name = value.get("license")
    if not isinstance(source, str) or not source.strip() or not isinstance(license_name, str) or not license_name.strip():
        return None
    result = {"source": source.strip(), "license": license_name.strip()}
    for key in ("path", "revision"):
        item = value.get(key)
        if item is not None:
            if not isinstance(item, str) or not item.strip():
                return None
            result[key] = item.strip()
    return result


def _validate_entity(entity: Any) -> dict[str, Any] | None:
    if not isinstance(entity, dict):
        return None
    platform = entity.get("platform")
    if platform not in SUPPORTED_PLATFORMS:
        return None
    config = entity.get("config")
    if not isinstance(config, dict) or not _json_structure_safe(config) or _contains_forbidden_keys(config):
        return None
    config = copy.deepcopy(config)

    advanced = config.get(CONF_ADVANCED_MAPPING)
    if advanced is not None:
        normalized_advanced = validate_advanced_mapping(advanced)
        if normalized_advanced is None:
            return None
        config[CONF_ADVANCED_MAPPING] = normalized_advanced

    raw_override_keys = entity.get("override_keys", [])
    if not isinstance(raw_override_keys, list):
        return None
    override_keys: list[str] = []
    for raw_key in raw_override_keys:
        if not isinstance(raw_key, str):
            return None
        key = raw_key.strip()
        token = _normalize_config_key(key)
        if not key or token in _PROTECTED_OVERRIDE_KEY_TOKENS or token in _FORBIDDEN_CONFIG_KEY_TOKENS or key not in config:
            return None
        if key not in override_keys:
            override_keys.append(key)

    extra = config.get(CONF_EXTRA_STATE_ATTRIBUTES_DPS)
    if extra is not None:
        if not isinstance(extra, dict) or not extra or len(extra) > 32:
            return None
        normalized_extra: dict[str, int] = {}
        for raw_name, raw_dp in extra.items():
            if not isinstance(raw_name, str):
                return None
            name = raw_name.strip()
            if not name or name in {"state", "raw_state"} or name in normalized_extra or isinstance(raw_dp, bool):
                return None
            try:
                dp_id = int(raw_dp)
            except (TypeError, ValueError):
                return None
            if dp_id <= 0 or dp_id > MAX_DP_ID:
                return None
            normalized_extra[name] = dp_id
        config[CONF_EXTRA_STATE_ATTRIBUTES_DPS] = normalized_extra

    configured_platform = config.get("platform")
    if configured_platform is not None and configured_platform != platform:
        return None
    primary_dp = config.get("id")
    if isinstance(primary_dp, bool):
        return None
    try:
        primary_dp = int(primary_dp)
    except (TypeError, ValueError):
        return None
    if primary_dp <= 0 or primary_dp > MAX_DP_ID:
        return None
    config["id"] = primary_dp
    config["platform"] = platform
    result = {"platform": platform, "config": config}
    if override_keys:
        result["override_keys"] = override_keys
    return result


def validate_catalog(payload: Any) -> dict[str, Any]:
    """Validate schema v1-v3 and normalize to the current schema."""
    if not isinstance(payload, dict):
        raise ValueError("Catalog root must be an object")
    schema_version = payload.get("schema_version")
    if schema_version not in SUPPORTED_CATALOG_SCHEMA_VERSIONS:
        raise ValueError("Unsupported catalog schema version")
    mappings = payload.get("mappings")
    if not isinstance(mappings, list):
        raise ValueError("Catalog mappings must be a list")
    if len(mappings) > MAX_CATALOG_MAPPINGS:
        raise ValueError("Catalog contains too many mappings")

    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_mapping in mappings:
        if not isinstance(raw_mapping, dict):
            continue
        mapping_id = raw_mapping.get("id")
        match = raw_mapping.get("match")
        entities = raw_mapping.get("entities")
        if not isinstance(mapping_id, str) or not mapping_id.strip() or not isinstance(match, dict) or not isinstance(entities, list):
            continue
        mapping_id = mapping_id.strip()
        if mapping_id in seen:
            raise ValueError(f"Duplicate catalog mapping ID: {mapping_id}")
        seen.add(mapping_id)

        fingerprint = None
        if schema_version == 1:
            raw_product = match.get("product_id")
            if not isinstance(raw_product, str) or not raw_product.strip():
                continue
            product_ids = [raw_product.strip()]
            optional_dps: list[int] = []
        else:
            fingerprint = _validate_fingerprint(match.get("fingerprint")) if schema_version >= 3 and match.get("fingerprint") is not None else None
            if schema_version >= 3 and match.get("fingerprint") is not None and fingerprint is None:
                continue
            product_ids = _normalize_product_ids(match.get("product_ids"), allow_empty=fingerprint is not None)
            optional_dps = _normalize_dps(match.get("optional_dps", []))
            if product_ids is None or optional_dps is None:
                continue
            # Fingerprints exist only for profiles lacking a trustworthy product ID.
            if fingerprint is not None and product_ids:
                continue

        category = match.get("category")
        if category is not None:
            if not isinstance(category, str):
                continue
            category = category.strip().lower() or None
        required_dps = _normalize_dps(match.get("required_dps", []))
        if required_dps is None or set(required_dps) & set(optional_dps):
            continue
        if fingerprint is not None and not required_dps:
            continue

        normalized_entities: list[dict[str, Any]] = []
        referenced: set[int] = set()
        valid = True
        for entity in entities:
            normalized = _validate_entity(entity)
            if normalized is None:
                valid = False
                break
            referenced.update(_config_dp_references(normalized["config"]))
            normalized_entities.append(normalized)
        if not valid or not normalized_entities:
            continue

        declared = set(required_dps) | set(optional_dps)
        if schema_version == 1:
            required_dps = sorted(set(required_dps) | referenced)
        elif not referenced.issubset(declared):
            continue
        if not required_dps:
            continue

        confidence = raw_mapping.get("confidence", "experimental")
        if not isinstance(confidence, str):
            continue
        confidence = confidence.strip().lower()
        if confidence not in {"experimental", "community", "verified"}:
            continue
        # Productless fingerprints can never self-promote to physically verified.
        if fingerprint is not None and confidence == "verified":
            continue

        provenance = _validate_provenance(raw_mapping.get("provenance"))
        if raw_mapping.get("provenance") is not None and provenance is None:
            continue
        normalized_match = {
            "product_ids": product_ids,
            "category": category,
            "required_dps": required_dps,
            "optional_dps": optional_dps,
        }
        if fingerprint is not None:
            normalized_match["fingerprint"] = fingerprint
        normalized_mapping = {
            "id": mapping_id,
            "match": normalized_match,
            "confidence": confidence,
            "entities": normalized_entities,
        }
        if provenance is not None:
            normalized_mapping["provenance"] = provenance
        validated.append(normalized_mapping)
    return {"schema_version": CATALOG_SCHEMA_VERSION, "mappings": validated}


def _validate_runtime_catalog(payload: Any) -> dict[str, Any]:
    validated = validate_catalog(payload)
    source = payload.get("mappings") if isinstance(payload, dict) else None
    if isinstance(source, list) and source and not validated["mappings"]:
        raise ValueError("Catalog contains no valid mappings")
    return validated


def _adapt_entity_for_available_dps(entity, optional_dps, available_dps):
    adapted = copy.deepcopy(entity)
    config = adapted["config"]
    primary_dp = int(config["id"])
    if primary_dp in optional_dps and primary_dp not in available_dps:
        return None
    removed: set[str] = set()

    extra = config.get(CONF_EXTRA_STATE_ATTRIBUTES_DPS)
    if isinstance(extra, dict):
        for name, value in list(extra.items()):
            dp_id = int(value)
            if dp_id in optional_dps and dp_id not in available_dps:
                del extra[name]
        if not extra:
            config.pop(CONF_EXTRA_STATE_ATTRIBUTES_DPS, None)
            removed.add(CONF_EXTRA_STATE_ATTRIBUTES_DPS)

    advanced = config.get(CONF_ADVANCED_MAPPING)
    if advanced is not None:
        pruned = prune_advanced_mapping(advanced, optional_dps, available_dps)
        if pruned is None:
            config.pop(CONF_ADVANCED_MAPPING, None)
            removed.add(CONF_ADVANCED_MAPPING)
        else:
            config[CONF_ADVANCED_MAPPING] = pruned

    for key, value in list(config.items()):
        if key in {"id", "platform"} or not _is_dp_reference_key(str(key)) or isinstance(value, bool):
            continue
        try:
            dp_id = int(value)
        except (TypeError, ValueError):
            continue
        if dp_id in optional_dps and dp_id not in available_dps:
            del config[key]
            removed.add(key)

    dependent = {
        "effect": ("effect_values",), "fan_preset_dp": ("fan_preset_values",),
        "fan_oscillating_control": ("fan_oscillating_on", "fan_oscillating_off"),
        "hvac_mode_dp": ("hvac_mode_values",), "hvac_action_dp": ("hvac_action_values",),
        "hvac_fan_mode_dp": ("hvac_fan_mode_values",), "hvac_swing_mode_dp": ("hvac_swing_mode_values",),
        "hvac_swing_horizontal_mode_dp": ("hvac_swing_horizontal_mode_values",),
        "preset_dp": ("preset_values",), "temperature_unit_dp": ("temperature_unit_values",),
        "target_temperature_low_dp": ("target_temperature_low_precision",),
        "target_temperature_high_dp": ("target_temperature_high_precision",),
        "target_humidity_dp": ("target_humidity_precision", "min_humidity_const", "max_humidity_const"),
        "current_humidity_dp": ("current_humidity_precision",),
        "cover_action_dp": ("cover_action_values",), "cover_open_dp": ("cover_open_values",),
        "set_position_dp": ("set_position_min", "set_position_max", "set_position_step", "set_position_inverted"),
        "current_position_dp": ("current_position_min", "current_position_max", "current_position_inverted"),
        "tilt_position_dp": ("tilt_position_min", "tilt_position_max", "tilt_position_step", "tilt_position_inverted"),
        "humidifier_switch_dp": ("humidifier_switch_on", "humidifier_switch_off"),
        "humidifier_mode_dp": ("humidifier_mode_values",), "humidifier_action_dp": ("humidifier_action_values",),
        "lock_state_dp": ("lock_state_values",), "lock_open_dp": ("lock_open_values", "lock_open_writable"),
        "lock_jammed_dp": ("lock_jammed_values",), "valve_switch_dp": ("valve_switch_on", "valve_switch_off"),
        "time_hms_dp": ("time_hms_format",),
        "water_heater_power_dp": ("water_heater_power_on", "water_heater_power_off"),
        "water_heater_temperature_unit_dp": ("water_heater_temperature_unit_values",),
        "water_heater_mode_dp": ("water_heater_mode_values", "water_heater_away_mode", "water_heater_default_mode"),
        "water_heater_away_dp": ("water_heater_away_on", "water_heater_away_off"),
        "siren_switch_dp": ("siren_switch_on", "siren_switch_off"),
        "siren_tone_dp": ("siren_tone_values", "siren_default_tone"),
        "siren_duration_dp": ("siren_duration_scaling",),
        "siren_volume_dp": ("siren_volume_values", "siren_volume_min", "siren_volume_max"),
        "alarm_state_dp": ("alarm_state_values",), "alarm_trigger_dp": ("alarm_trigger_on", "alarm_trigger_off"),
        "event_dp": ("event_types", "event_device_class"), "camera_switch_dp": ("camera_switch_on", "camera_switch_off"),
        "camera_snapshot_dp": ("camera_snapshot_encoding",), "camera_record_dp": ("camera_record_on", "camera_record_off"),
        "camera_motion_dp": ("camera_motion_on", "camera_motion_off"),
        "datetime_timestamp_dp": ("datetime_timestamp_scaling",),
        "lawn_mower_activity_dp": ("lawn_mower_activity_values",), "lawn_mower_command_dp": ("lawn_mower_command_values",),
        "remote_send_dp": ("remote_send_command", "remote_rf_send_command", "remote_learn_command", "remote_learn_exit_command", "remote_rf_learn_command", "remote_rf_learn_exit_command"),
        "infrared_send_dp": ("infrared_send_command",),
    }
    for reference in tuple(removed):
        for key in dependent.get(reference, ()):
            if key in config:
                config.pop(key, None)
                removed.add(key)
    override_keys = adapted.get("override_keys")
    if isinstance(override_keys, list) and removed:
        kept = [key for key in override_keys if key not in removed]
        if kept:
            adapted["override_keys"] = kept
        else:
            adapted.pop("override_keys", None)
    return adapted


def _mapping_compatible(mapping, product_id, category, available_dps):
    match = mapping["match"]
    product_ids = tuple(match.get("product_ids", ()))
    fingerprint = match.get("fingerprint")
    if product_ids:
        if not product_id or product_id not in product_ids:
            return None
        kind = "product"
    else:
        if product_id or fingerprint != {"mode": "exact_dps"}:
            return None
        declared = set(match.get("required_dps", [])) | set(match.get("optional_dps", []))
        # Fail closed: a productless profile may not explain only a subset of
        # the observed LAN surface. Every observed DP must be declared.
        if available_dps - declared:
            return None
        kind = "fingerprint"

    expected_category = match.get("category")
    if expected_category and category and category != expected_category:
        return None
    required = set(match.get("required_dps", []))
    optional = set(match.get("optional_dps", []))
    if not required.issubset(available_dps):
        return None
    entities = tuple(
        adapted for entity in mapping["entities"]
        if (adapted := _adapt_entity_for_available_dps(entity, optional, available_dps)) is not None
    )
    if not entities:
        return None
    score = len(required) * 4 + len(optional & available_dps)
    if expected_category and category == expected_category:
        score += 10
    if kind == "product":
        score += 1000
    return kind, score, entities


def match_catalog_mapping(catalog, device, available_dps, *, source="remote"):
    """Find a product match, or an unambiguous exact-DPS fingerprint."""
    if not catalog:
        return None
    product_id = _device_product_id(device)
    category = _device_category(device)
    candidates = []
    for mapping in catalog.get("mappings", []):
        compatible = _mapping_compatible(mapping, product_id, category, available_dps)
        if compatible is not None:
            kind, score, entities = compatible
            candidates.append((score, mapping, entities, kind))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score = candidates[0][0]
    best = [item for item in candidates if item[0] == best_score]
    # Product IDs are authoritative. Fingerprints are not: an equal best score
    # means the LAN surface cannot uniquely identify a profile, so match none.
    if len(best) != 1 and best[0][3] == "fingerprint":
        _LOGGER.debug("Rejecting ambiguous LocalTuya fingerprint match: %s candidates", len(best))
        return None
    _, mapping, entities, kind = best[0]
    match = mapping["match"]
    provenance = mapping.get("provenance")
    return CatalogMatch(
        mapping_id=mapping["id"], product_id=product_id or "",
        confidence=mapping["confidence"], required_dps=tuple(match["required_dps"]),
        entities=entities, source=source, product_ids=tuple(match.get("product_ids", ())),
        optional_dps=tuple(match.get("optional_dps", ())),
        provenance=copy.deepcopy(provenance) if provenance else None,
        match_kind=kind,
    )


def load_builtin_catalog(path: Path = BUILTIN_CATALOG_PATH):
    try:
        validated = validate_catalog(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as ex:
        _LOGGER.error("Unable to load bundled LocalTuya device catalog: %s", ex)
        return {"schema_version": CATALOG_SCHEMA_VERSION, "mappings": []}
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "mappings": [mapping for mapping in validated["mappings"] if mapping["confidence"] == "verified"],
    }


class DeviceCatalog:
    """Remote LocalTuya device catalog with persistent fallback."""

    def __init__(self, hass, *, url=CATALOG_URL, session=None, store=None):
        self._hass = hass
        self._url = url
        self._builtin_catalog = {"schema_version": CATALOG_SCHEMA_VERSION, "mappings": []}
        self._session = session if session is not None else async_get_clientsession(hass)
        self._store = store if store is not None else Store(hass, CATALOG_STORAGE_VERSION, CATALOG_STORAGE_KEY)
        self._catalog = None
        self._etag = None
        self._cache_loaded = False

    async def async_load_builtin_catalog(self):
        try:
            catalog = load_builtin_catalog() if self._hass is None else await self._hass.async_add_executor_job(load_builtin_catalog)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Unable to load bundled LocalTuya device catalog asynchronously: %s", ex)
            return False
        self._builtin_catalog = catalog
        return True

    @property
    def catalog(self):
        return self._catalog

    @property
    def bundled_mapping_count(self):
        return len(self._builtin_catalog.get("mappings", []))

    @property
    def remote_mapping_count(self):
        return 0 if self._catalog is None else len(self._catalog.get("mappings", []))

    @property
    def mapping_count(self):
        return self.remote_mapping_count if self._catalog is not None else self.bundled_mapping_count

    @property
    def cache_loaded(self):
        return self._cache_loaded

    async def async_load_cache(self):
        try:
            stored = await self._store.async_load()
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.debug("Unable to load LocalTuya device catalog cache: %s", ex)
            return False
        if not isinstance(stored, dict) or stored.get("url") != self._url:
            return False
        try:
            validated = _validate_runtime_catalog(stored.get("catalog"))
        except ValueError as ex:
            _LOGGER.debug("Ignoring invalid cached LocalTuya catalog: %s", ex)
            return False
        self._catalog = validated
        self._cache_loaded = True
        if isinstance(stored.get("etag"), str):
            self._etag = stored["etag"]
        return True

    async def _async_save_cache(self):
        if self._catalog is None:
            return False
        try:
            await self._store.async_save({"url": self._url, "etag": self._etag, "catalog": self._catalog})
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.debug("Unable to save LocalTuya device catalog cache: %s", ex)
            return False
        return True

    async def async_refresh(self):
        headers = {"If-None-Match": self._etag} if self._etag else {}
        try:
            async with self._session.get(self._url, headers=headers, timeout=REQUEST_TIMEOUT) as response:
                if response.status == 304:
                    return self._catalog is not None
                if response.status != 200:
                    return False
                if isinstance(response.content_length, int) and response.content_length > MAX_REMOTE_CATALOG_BYTES:
                    return False
                payload = await response.json(content_type=None)
                if len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > MAX_REMOTE_CATALOG_BYTES:
                    return False
                validated = _validate_runtime_catalog(payload)
                self._catalog = validated
                etag = response.headers.get("ETag")
                self._etag = etag if isinstance(etag, str) else None
                await self._async_save_cache()
                return True
        except (ClientError, TimeoutError, ValueError) as ex:
            _LOGGER.debug("Unable to refresh LocalTuya device catalog: %s", ex)
            return False

    def match(self, device, available_dps):
        remote = match_catalog_mapping(self._catalog, device, available_dps, source="remote")
        bundled = match_catalog_mapping(self._builtin_catalog, device, available_dps, source="bundled")
        if remote is None:
            return bundled
        if bundled is None:
            return remote
        rank = {"experimental": 0, "community": 1, "verified": 2}
        return bundled if rank.get(remote.confidence, 0) < rank.get(bundled.confidence, 0) else remote
