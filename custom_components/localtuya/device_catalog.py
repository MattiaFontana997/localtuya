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

from .const import CONF_EXTRA_STATE_ATTRIBUTES_DPS, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CATALOG_SCHEMA_VERSION = 2
SUPPORTED_CATALOG_SCHEMA_VERSIONS = {1, 2}

CATALOG_URL = (
    "https://raw.githubusercontent.com/"
    "MattiaFontana997/localtuya-device-catalog/"
    "main/catalog.json"
)

REQUEST_TIMEOUT = ClientTimeout(total=10)
MAX_REMOTE_CATALOG_BYTES = 2 * 1024 * 1024
MAX_CATALOG_MAPPINGS = 2048
MAX_PRODUCT_IDS = 64
MAX_DP_ID = 65535
MAX_CONFIG_DEPTH = 12
MAX_CONFIG_NODES = 4096

BUILTIN_CATALOG_PATH = Path(__file__).with_name("builtin_catalog.json")
CATALOG_STORAGE_VERSION = 1
CATALOG_STORAGE_KEY = "localtuya.device_catalog"

# Keep catalog acceptance aligned with the platforms exposed by LocalTuya's
# config flow. A new runtime must never be silently rejected by a stale second
# allowlist here.
SUPPORTED_PLATFORMS = frozenset(PLATFORMS)

_FORBIDDEN_CONFIG_KEYS = {
    "local_key",
    "device_id",
    "host",
    "ip",
    "gwid",
    "client_id",
    "client_secret",
    "user_id",
    "username",
    "region",
}

_PROTECTED_OVERRIDE_KEYS = {
    "id",
    "platform",
    "friendly_name",
}

_DP_REFERENCE_KEYS = {
    "id",
    "brightness",
    "color_temp",
    "color_mode",
    "color",
    "scene",
    "effect",
    "current",
    "current_consumption",
    "voltage",
    "fan_speed_control",
    "fan_oscillating_control",
    "fan_direction",
}

_PROVENANCE_KEYS = {
    "source",
    "path",
    "revision",
    "license",
}


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


def _device_product_id(device: dict[str, Any]) -> str | None:
    """Extract product ID/key from Tuya metadata."""
    for key in ("product_id", "productId", "product_key", "productKey"):
        value = device.get(key)
        if value:
            return str(value).strip()
    return None


def _device_category(device: dict[str, Any]) -> str:
    """Extract Tuya category."""
    value = device.get("category")
    return str(value).strip().lower() if value else ""


def _normalize_config_key(value: Any) -> str:
    """Normalize config keys to block separator/case bypasses."""
    return "".join(
        char for char in str(value).casefold() if char.isalnum()
    )


_FORBIDDEN_CONFIG_KEY_TOKENS = {
    _normalize_config_key(key) for key in _FORBIDDEN_CONFIG_KEYS
}
_PROTECTED_OVERRIDE_KEY_TOKENS = {
    _normalize_config_key(key) for key in _PROTECTED_OVERRIDE_KEYS
}


def _json_structure_safe(value: Any) -> bool:
    """Validate nesting and complexity of catalog values."""
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
            for child in current:
                stack.append((child, depth + 1))
        elif not isinstance(current, (str, int, float, bool, type(None))):
            return False

    return True


def _contains_forbidden_keys(value: Any) -> bool:
    """Return whether a JSON value contains forbidden config keys."""
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
    """Return DP IDs referenced by a LocalTuya entity config."""
    result: set[int] = set()

    extra_attributes = config.get(CONF_EXTRA_STATE_ATTRIBUTES_DPS)
    if isinstance(extra_attributes, dict):
        for value in extra_attributes.values():
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
    return result


def _normalize_dps(value: Any) -> list[int] | None:
    """Normalize one required/optional DP list."""
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


def _normalize_product_ids(value: Any) -> list[str] | None:
    """Normalize one schema-v2 product ID list."""
    if not isinstance(value, list) or not value or len(value) > MAX_PRODUCT_IDS:
        return None

    result: list[str] = []
    for raw_product_id in value:
        if not isinstance(raw_product_id, str):
            return None
        product_id = raw_product_id.strip()
        if not product_id:
            return None
        if product_id not in result:
            result.append(product_id)
    return sorted(result)


def _validate_provenance(value: Any) -> dict[str, str] | None:
    """Validate optional non-executable source attribution metadata."""
    if value is None:
        return None
    if not isinstance(value, dict) or not _json_structure_safe(value):
        return None
    if set(value) - _PROVENANCE_KEYS:
        return None

    source = value.get("source")
    license_name = value.get("license")
    if not isinstance(source, str) or not source.strip():
        return None
    if not isinstance(license_name, str) or not license_name.strip():
        return None

    result = {
        "source": source.strip(),
        "license": license_name.strip(),
    }
    for key in ("path", "revision"):
        item = value.get(key)
        if item is not None:
            if not isinstance(item, str) or not item.strip():
                return None
            result[key] = item.strip()
    return result


def _validate_entity(entity: Any) -> dict[str, Any] | None:
    """Validate one catalog entity without allowing arbitrary code."""
    if not isinstance(entity, dict):
        return None

    platform = entity.get("platform")
    if platform not in SUPPORTED_PLATFORMS:
        return None

    config = entity.get("config")
    if not isinstance(config, dict):
        return None
    if not _json_structure_safe(config) or _contains_forbidden_keys(config):
        return None

    raw_override_keys = entity.get("override_keys", [])
    if not isinstance(raw_override_keys, list):
        return None

    override_keys: list[str] = []
    for raw_key in raw_override_keys:
        if not isinstance(raw_key, str):
            return None
        key = raw_key.strip()
        normalized_key = _normalize_config_key(key)
        if (
            not key
            or normalized_key in _PROTECTED_OVERRIDE_KEY_TOKENS
            or normalized_key in _FORBIDDEN_CONFIG_KEY_TOKENS
            or key not in config
        ):
            return None
        if key not in override_keys:
            override_keys.append(key)

    config = copy.deepcopy(config)

    extra_attributes = config.get(CONF_EXTRA_STATE_ATTRIBUTES_DPS)
    if extra_attributes is not None:
        if not isinstance(extra_attributes, dict) or not extra_attributes:
            return None
        if len(extra_attributes) > 32:
            return None
        normalized_extra: dict[str, int] = {}
        for raw_name, raw_dp in extra_attributes.items():
            if not isinstance(raw_name, str):
                return None
            name = raw_name.strip()
            if not name or name in {"state", "raw_state"} or name in normalized_extra:
                return None
            if isinstance(raw_dp, bool):
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

    validated = {"platform": platform, "config": config}
    if override_keys:
        validated["override_keys"] = override_keys
    return validated


def validate_catalog(payload: Any) -> dict[str, Any]:
    """Validate and normalize schema-v1/v2 catalogs to schema v2."""
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
    seen_mapping_ids: set[str] = set()

    for raw_mapping in mappings:
        if not isinstance(raw_mapping, dict):
            continue

        mapping_id = raw_mapping.get("id")
        match = raw_mapping.get("match")
        entities = raw_mapping.get("entities")
        if (
            not isinstance(mapping_id, str)
            or not mapping_id.strip()
            or not isinstance(match, dict)
            or not isinstance(entities, list)
        ):
            continue

        mapping_id = mapping_id.strip()
        if mapping_id in seen_mapping_ids:
            raise ValueError(f"Duplicate catalog mapping ID: {mapping_id}")
        seen_mapping_ids.add(mapping_id)

        if schema_version == 1:
            raw_product_id = match.get("product_id")
            if not isinstance(raw_product_id, str) or not raw_product_id.strip():
                continue
            product_ids = [raw_product_id.strip()]
            optional_dps: list[int] = []
        else:
            product_ids = _normalize_product_ids(match.get("product_ids"))
            optional_dps = _normalize_dps(match.get("optional_dps", []))
            if product_ids is None or optional_dps is None:
                continue

        category = match.get("category")
        if category is not None:
            if not isinstance(category, str):
                continue
            category = category.strip().lower() or None

        required_dps = _normalize_dps(match.get("required_dps", []))
        if required_dps is None:
            continue

        if set(required_dps) & set(optional_dps):
            continue

        validated_entities: list[dict[str, Any]] = []
        referenced_dps: set[int] = set()
        mapping_entities_valid = True

        for entity in entities:
            normalized = _validate_entity(entity)
            if normalized is None:
                mapping_entities_valid = False
                break
            referenced_dps.update(_config_dp_references(normalized["config"]))
            validated_entities.append(normalized)

        if not mapping_entities_valid or not validated_entities:
            continue

        declared_dps = set(required_dps) | set(optional_dps)
        if schema_version == 1:
            # Preserve V1 behaviour: entity DP references implicitly became
            # required even when the source catalog omitted them.
            required_dps = sorted(set(required_dps) | referenced_dps)
        elif not referenced_dps.issubset(declared_dps):
            continue

        if not required_dps:
            continue

        raw_confidence = raw_mapping.get("confidence", "experimental")
        if not isinstance(raw_confidence, str):
            continue
        confidence = raw_confidence.strip().lower()
        if confidence not in {"experimental", "community", "verified"}:
            continue

        provenance = _validate_provenance(raw_mapping.get("provenance"))
        if raw_mapping.get("provenance") is not None and provenance is None:
            continue

        normalized_mapping: dict[str, Any] = {
            "id": mapping_id,
            "match": {
                "product_ids": product_ids,
                "category": category,
                "required_dps": required_dps,
                "optional_dps": optional_dps,
            },
            "confidence": confidence,
            "entities": validated_entities,
        }
        if provenance is not None:
            normalized_mapping["provenance"] = provenance
        validated.append(normalized_mapping)

    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "mappings": validated,
    }


def _validate_runtime_catalog(payload: Any) -> dict[str, Any]:
    """Validate cache/remote catalog without accepting a silent wipe."""
    validated = validate_catalog(payload)
    source_mappings = payload.get("mappings") if isinstance(payload, dict) else None
    if (
        isinstance(source_mappings, list)
        and source_mappings
        and not validated["mappings"]
    ):
        raise ValueError("Catalog contains no valid mappings")
    return validated


def _adapt_entity_for_available_dps(
    entity: dict[str, Any],
    optional_dps: set[int],
    available_dps: set[int],
) -> dict[str, Any] | None:
    """Remove capabilities backed only by absent optional DPS."""
    adapted = copy.deepcopy(entity)
    config = adapted["config"]
    primary_dp = int(config["id"])

    if primary_dp in optional_dps and primary_dp not in available_dps:
        return None

    removed_keys: set[str] = set()

    extra_attributes = config.get(CONF_EXTRA_STATE_ATTRIBUTES_DPS)
    if isinstance(extra_attributes, dict):
        for name, value in list(extra_attributes.items()):
            dp_id = int(value)
            if dp_id in optional_dps and dp_id not in available_dps:
                del extra_attributes[name]
        if not extra_attributes:
            del config[CONF_EXTRA_STATE_ATTRIBUTES_DPS]
            removed_keys.add(CONF_EXTRA_STATE_ATTRIBUTES_DPS)

    for key, value in list(config.items()):
        if key in {"id", "platform"} or not _is_dp_reference_key(str(key)):
            continue
        if isinstance(value, bool):
            continue
        try:
            dp_id = int(value)
        except (TypeError, ValueError):
            continue
        if dp_id in optional_dps and dp_id not in available_dps:
            del config[key]
            removed_keys.add(key)

    dependent_config = {
        "effect": ("effect_values",),
        "fan_preset_dp": ("fan_preset_values",),
        "fan_oscillating_control": ("fan_oscillating_on", "fan_oscillating_off"),
        "hvac_mode_dp": ("hvac_mode_values",),
        "hvac_action_dp": ("hvac_action_values",),
        "hvac_fan_mode_dp": ("hvac_fan_mode_values",),
        "hvac_swing_mode_dp": ("hvac_swing_mode_values",),
        "hvac_swing_horizontal_mode_dp": ("hvac_swing_horizontal_mode_values",),
        "preset_dp": ("preset_values",),
        "temperature_unit_dp": ("temperature_unit_values",),
        "target_temperature_low_dp": ("target_temperature_low_precision",),
        "target_temperature_high_dp": ("target_temperature_high_precision",),
        "target_humidity_dp": ("target_humidity_precision", "min_humidity_const", "max_humidity_const"),
        "current_humidity_dp": ("current_humidity_precision",),
        "cover_action_dp": ("cover_action_values",),
        "cover_open_dp": ("cover_open_values",),
        "set_position_dp": (
            "set_position_min", "set_position_max", "set_position_step",
            "set_position_inverted",
        ),
        "current_position_dp": (
            "current_position_min", "current_position_max",
            "current_position_inverted",
        ),
        "tilt_position_dp": (
            "tilt_position_min", "tilt_position_max", "tilt_position_step",
            "tilt_position_inverted",
        ),
        "humidifier_switch_dp": ("humidifier_switch_on", "humidifier_switch_off"),
        "humidifier_mode_dp": ("humidifier_mode_values",),
        "humidifier_action_dp": ("humidifier_action_values",),
        "lock_state_dp": ("lock_state_values",),
        "lock_open_dp": ("lock_open_values", "lock_open_writable"),
        "lock_jammed_dp": ("lock_jammed_values",),
        "valve_switch_dp": ("valve_switch_on", "valve_switch_off"),
        "valve_current_position_dp": (),
        "time_hms_dp": ("time_hms_format",),
        "water_heater_power_dp": ("water_heater_power_on", "water_heater_power_off"),
        "water_heater_temperature_unit_dp": ("water_heater_temperature_unit_values",),
        "water_heater_mode_dp": (
            "water_heater_mode_values", "water_heater_away_mode",
            "water_heater_default_mode",
        ),
        "water_heater_away_dp": ("water_heater_away_on", "water_heater_away_off"),
        "siren_switch_dp": ("siren_switch_on", "siren_switch_off"),
        "siren_tone_dp": ("siren_tone_values", "siren_default_tone"),
        "siren_duration_dp": ("siren_duration_scaling",),
        "siren_volume_dp": (
            "siren_volume_values", "siren_volume_min", "siren_volume_max",
        ),
        "alarm_state_dp": ("alarm_state_values",),
        "alarm_trigger_dp": ("alarm_trigger_on", "alarm_trigger_off"),
        "event_dp": ("event_types", "event_device_class"),
        "camera_switch_dp": ("camera_switch_on", "camera_switch_off"),
        "camera_snapshot_dp": ("camera_snapshot_encoding",),
        "camera_record_dp": ("camera_record_on", "camera_record_off"),
        "camera_motion_dp": ("camera_motion_on", "camera_motion_off"),
        "datetime_timestamp_dp": ("datetime_timestamp_scaling",),
        "lawn_mower_activity_dp": ("lawn_mower_activity_values",),
        "lawn_mower_command_dp": ("lawn_mower_command_values",),
        "remote_send_dp": (
            "remote_send_command", "remote_rf_send_command",
            "remote_learn_command", "remote_learn_exit_command",
            "remote_rf_learn_command", "remote_rf_learn_exit_command",
        ),
        "infrared_send_dp": ("infrared_send_command",),
    }
    for reference_key in tuple(removed_keys):
        for dependent_key in dependent_config.get(reference_key, ()):
            if dependent_key in config:
                config.pop(dependent_key, None)
                removed_keys.add(dependent_key)

    override_keys = adapted.get("override_keys")
    if isinstance(override_keys, list) and removed_keys:
        override_keys = [key for key in override_keys if key not in removed_keys]
        if override_keys:
            adapted["override_keys"] = override_keys
        else:
            adapted.pop("override_keys", None)

    return adapted


def match_catalog_mapping(
    catalog: dict[str, Any] | None,
    device: dict[str, Any],
    available_dps: set[int],
    *,
    source: str = "remote",
) -> CatalogMatch | None:
    """Find the best compatible catalog mapping."""
    if not catalog:
        return None

    product_id = _device_product_id(device)
    if not product_id:
        return None
    category = _device_category(device)

    best_mapping: dict[str, Any] | None = None
    best_entities: tuple[dict[str, Any], ...] = ()
    best_score = -1

    for mapping in catalog.get("mappings", []):
        match = mapping["match"]
        product_ids = tuple(match.get("product_ids", ()))
        if product_id not in product_ids:
            continue

        expected_category = match.get("category")
        required_dps = set(match.get("required_dps", []))
        optional_dps = set(match.get("optional_dps", []))

        if not required_dps.issubset(available_dps):
            continue

        if expected_category:
            if category and category != expected_category:
                continue

        adapted_entities = tuple(
            adapted
            for entity in mapping["entities"]
            if (
                adapted := _adapt_entity_for_available_dps(
                    entity,
                    optional_dps,
                    available_dps,
                )
            )
            is not None
        )
        if not adapted_entities:
            continue

        score = 100 + len(required_dps)
        score += len(optional_dps & available_dps)
        if expected_category and category == expected_category:
            score += 10

        if score <= best_score:
            continue

        best_score = score
        best_mapping = mapping
        best_entities = adapted_entities

    if best_mapping is None:
        return None

    match = best_mapping["match"]
    provenance = best_mapping.get("provenance")
    return CatalogMatch(
        mapping_id=best_mapping["id"],
        product_id=product_id,
        confidence=best_mapping["confidence"],
        required_dps=tuple(match["required_dps"]),
        entities=best_entities,
        source=source,
        product_ids=tuple(match["product_ids"]),
        optional_dps=tuple(match["optional_dps"]),
        provenance=copy.deepcopy(provenance) if provenance else None,
    )


def load_builtin_catalog(
    path: Path = BUILTIN_CATALOG_PATH,
) -> dict[str, Any]:
    """Load the bundled physically verified catalog snapshot."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        validated = validate_catalog(payload)
    except (OSError, ValueError) as ex:
        _LOGGER.error("Unable to load bundled LocalTuya device catalog: %s", ex)
        return {"schema_version": CATALOG_SCHEMA_VERSION, "mappings": []}

    mappings = [
        mapping
        for mapping in validated["mappings"]
        if mapping["confidence"] == "verified"
    ]
    return {"schema_version": CATALOG_SCHEMA_VERSION, "mappings": mappings}


class DeviceCatalog:
    """Remote LocalTuya device catalog with persistent fallback."""

    def __init__(
        self,
        hass,
        *,
        url: str = CATALOG_URL,
        session: Any | None = None,
        store: Any | None = None,
    ) -> None:
        self._hass = hass
        self._url = url
        self._builtin_catalog = {
            "schema_version": CATALOG_SCHEMA_VERSION,
            "mappings": [],
        }
        self._session = (
            session if session is not None else async_get_clientsession(hass)
        )
        self._store = (
            store
            if store is not None
            else Store(hass, CATALOG_STORAGE_VERSION, CATALOG_STORAGE_KEY)
        )
        self._catalog: dict[str, Any] | None = None
        self._etag: str | None = None
        self._cache_loaded = False

    async def async_load_builtin_catalog(self) -> bool:
        """Load bundled catalog without blocking the HA event loop."""
        try:
            if self._hass is None:
                catalog = load_builtin_catalog()
            else:
                catalog = await self._hass.async_add_executor_job(
                    load_builtin_catalog
                )
        except Exception as ex:
            _LOGGER.error(
                "Unable to load bundled LocalTuya device catalog "
                "asynchronously: %s",
                ex,
            )
            return False

        self._builtin_catalog = catalog
        return True

    @property
    def catalog(self) -> dict[str, Any] | None:
        return self._catalog

    @property
    def bundled_mapping_count(self) -> int:
        return len(self._builtin_catalog.get("mappings", []))

    @property
    def remote_mapping_count(self) -> int:
        if self._catalog is None:
            return 0
        return len(self._catalog.get("mappings", []))

    @property
    def mapping_count(self) -> int:
        return (
            self.remote_mapping_count
            if self._catalog is not None
            else self.bundled_mapping_count
        )

    @property
    def cache_loaded(self) -> bool:
        return self._cache_loaded

    async def async_load_cache(self) -> bool:
        """Restore last valid catalog from Home Assistant storage."""
        try:
            stored = await self._store.async_load()
        except Exception as ex:
            _LOGGER.debug("Unable to load LocalTuya device catalog cache: %s", ex)
            return False

        if not isinstance(stored, dict):
            return False
        if stored.get("url") != self._url:
            _LOGGER.debug(
                "Ignoring LocalTuya device catalog cache from a different URL"
            )
            return False

        try:
            validated = _validate_runtime_catalog(stored.get("catalog"))
        except ValueError as ex:
            _LOGGER.debug("Ignoring invalid cached LocalTuya catalog: %s", ex)
            return False

        self._catalog = validated
        self._cache_loaded = True
        etag = stored.get("etag")
        if isinstance(etag, str):
            self._etag = etag

        _LOGGER.info(
            "Loaded cached LocalTuya device catalog with %s mappings",
            self.mapping_count,
        )
        return True

    async def _async_save_cache(self) -> bool:
        """Persist currently valid catalog."""
        if self._catalog is None:
            return False
        try:
            await self._store.async_save(
                {
                    "url": self._url,
                    "etag": self._etag,
                    "catalog": self._catalog,
                }
            )
        except Exception as ex:
            _LOGGER.debug("Unable to save LocalTuya device catalog cache: %s", ex)
            return False
        return True

    async def async_refresh(self) -> bool:
        """Download and validate latest catalog without replacing good state on failure."""
        headers = {}
        if self._etag:
            headers["If-None-Match"] = self._etag

        try:
            async with self._session.get(
                self._url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status == 304:
                    return self._catalog is not None
                if response.status != 200:
                    _LOGGER.debug(
                        "Remote device catalog returned HTTP %s", response.status
                    )
                    return False

                content_length = getattr(response, "content_length", None)
                if (
                    isinstance(content_length, int)
                    and content_length > MAX_REMOTE_CATALOG_BYTES
                ):
                    _LOGGER.warning(
                        "Remote LocalTuya device catalog exceeds the maximum "
                        "allowed size"
                    )
                    return False

                payload = await response.json(content_type=None)
                encoded_size = len(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
                if encoded_size > MAX_REMOTE_CATALOG_BYTES:
                    _LOGGER.warning(
                        "Remote LocalTuya device catalog exceeds the maximum "
                        "allowed size"
                    )
                    return False

                validated = _validate_runtime_catalog(payload)
                self._catalog = validated
                etag = response.headers.get("ETag")
                self._etag = etag if isinstance(etag, str) else None
                await self._async_save_cache()

                _LOGGER.info(
                    "Loaded remote LocalTuya device catalog with %s mappings",
                    self.mapping_count,
                )
                return True

        except (ClientError, TimeoutError, ValueError) as ex:
            _LOGGER.debug("Unable to refresh LocalTuya device catalog: %s", ex)
            return False

    def match(
        self,
        device: dict[str, Any],
        available_dps: set[int],
    ) -> CatalogMatch | None:
        """Return the safest compatible product-specific mapping."""
        remote_match = match_catalog_mapping(
            self._catalog,
            device,
            available_dps,
            source="remote",
        )
        bundled_match = match_catalog_mapping(
            self._builtin_catalog,
            device,
            available_dps,
            source="bundled",
        )

        if remote_match is None:
            return bundled_match
        if bundled_match is None:
            return remote_match

        confidence_rank = {
            "experimental": 0,
            "community": 1,
            "verified": 2,
        }
        if confidence_rank.get(remote_match.confidence, 0) < confidence_rank.get(
            bundled_match.confidence, 0
        ):
            return bundled_match
        return remote_match
