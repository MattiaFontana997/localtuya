"""Sanitized LocalTuya community mapping export."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from homeassistant.const import (
    CONF_ENTITIES,
    CONF_FRIENDLY_NAME,
    CONF_ID,
    CONF_PLATFORM,
)

from .const import (
    CONF_DPS_STRINGS,
    CONF_PRODUCT_KEY,
    CONF_PROTOCOL_VERSION,
)
from .device_catalog import (
    CATALOG_SCHEMA_VERSION,
    SUPPORTED_PLATFORMS,
)

# Entity fields whose values are DP identifiers but whose names
# do not end in "_dp".
_EXPLICIT_DP_REFERENCE_KEYS = {
    "brightness",
    "color_temp",
    "color_mode",
    "color",
    "scene",
    "current",
    "current_consumption",
    "voltage",
    "fan_speed_control",
    "fan_oscillating_control",
    "fan_direction",
}

# These values must never be exported even if a malformed/manual
# entity configuration happened to contain them.
_SENSITIVE_ENTITY_KEYS = {
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


def _json_clone(
    value: Any,
) -> Any:
    """Clone a value while guaranteeing JSON serializability."""
    try:
        return json.loads(
            json.dumps(value)
        )
    except (
        TypeError,
        ValueError,
    ) as ex:
        raise ValueError(
            "Mapping contains non-JSON configuration"
        ) from ex


def _scrub_sensitive_keys(
    value: Any,
) -> Any:
    """Recursively remove sensitive keys from exported JSON."""
    if isinstance(value, dict):
        result = {}

        for key, child in value.items():
            normalized_key = (
                str(key)
                .strip()
                .lower()
            )

            if (
                normalized_key
                in _SENSITIVE_ENTITY_KEYS
            ):
                continue

            result[key] = (
                _scrub_sensitive_keys(
                    child
                )
            )

        return result

    if isinstance(value, list):
        return [
            _scrub_sensitive_keys(
                item
            )
            for item in value
        ]

    return value


def _sanitize_entity(
    entity: Any,
) -> dict[str, Any] | None:
    """Create a privacy-safe catalog entity."""
    if not isinstance(entity, dict):
        return None

    platform = entity.get(
        CONF_PLATFORM
    )

    if platform not in SUPPORTED_PLATFORMS:
        return None

    primary_dp = entity.get(
        CONF_ID
    )

    if isinstance(primary_dp, bool):
        return None

    try:
        primary_dp = int(
            primary_dp
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    if primary_dp <= 0:
        return None

    config = _json_clone(
        entity
    )

    config = _scrub_sensitive_keys(
        config
    )

    # Friendly names may contain room names, people names,
    # addresses or other user-specific information.
    config.pop(
        CONF_FRIENDLY_NAME,
        None,
    )

    config[CONF_ID] = primary_dp
    config[CONF_PLATFORM] = platform

    return {
        "platform": platform,
        "config": config,
    }


def _parse_observed_dps(
    device_data: dict[str, Any],
) -> list[int]:
    """Parse stored LocalTuya DPS fingerprint."""
    dps_strings = device_data.get(
        CONF_DPS_STRINGS,
        [],
    )

    if not isinstance(
        dps_strings,
        (list, tuple),
    ):
        return []

    result: set[int] = set()

    for raw_value in dps_strings:
        token = (
            str(raw_value)
            .strip()
            .split(" ", 1)[0]
        )

        try:
            dp_id = int(token)
        except (
            TypeError,
            ValueError,
        ):
            continue

        if dp_id > 0:
            result.add(dp_id)

    return sorted(result)


def _is_dp_reference_key(
    key: str,
) -> bool:
    """Return whether a config key contains a DP identifier."""
    if key == CONF_ID:
        return True

    if key.endswith("_dp"):
        return True

    return (
        key
        in _EXPLICIT_DP_REFERENCE_KEYS
    )


def _collect_required_dps(
    entities: list[dict[str, Any]],
) -> list[int]:
    """Collect every DP referenced by exported entity configuration."""
    result: set[int] = set()

    for entity in entities:
        config = entity["config"]

        for key, value in config.items():
            if not _is_dp_reference_key(
                str(key)
            ):
                continue

            if isinstance(value, bool):
                continue

            try:
                dp_id = int(value)
            except (
                TypeError,
                ValueError,
            ):
                continue

            if dp_id > 0:
                result.add(dp_id)

    return sorted(result)


def _find_product_id(
    device_data: dict[str, Any],
    cloud_device: dict[str, Any],
) -> str | None:
    """Find a stable Tuya product identifier."""
    for source in (
        cloud_device,
        device_data,
    ):
        for key in (
            "product_id",
            "productId",
            "product_key",
            "productKey",
            CONF_PRODUCT_KEY,
        ):
            value = source.get(key)

            if value:
                return (
                    str(value)
                    .strip()
                )

    return None


def _find_category(
    device_data: dict[str, Any],
    cloud_device: dict[str, Any],
) -> str | None:
    """Find Tuya product category."""
    for source in (
        cloud_device,
        device_data,
    ):
        value = source.get(
            "category"
        )

        if value:
            return (
                str(value)
                .strip()
                .lower()
            )

    return None


def _safe_mapping_id_part(
    value: str,
) -> str:
    """Create a safe catalog mapping identifier fragment."""
    value = re.sub(
        r"[^A-Za-z0-9._-]+",
        "-",
        value,
    ).strip("-")

    return value or "tuya-product"


def build_mapping_submission(
    device_data: dict[str, Any],
    *,
    cloud_device: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a privacy-safe community catalog submission."""
    if not isinstance(
        device_data,
        dict,
    ):
        raise ValueError(
            "Invalid LocalTuya device configuration"
        )

    cloud_device = (
        cloud_device
        if isinstance(
            cloud_device,
            dict,
        )
        else {}
    )

    product_id = _find_product_id(
        device_data,
        cloud_device,
    )

    if not product_id:
        raise ValueError(
            "No stable Tuya product identifier is available"
        )

    raw_entities = device_data.get(
        CONF_ENTITIES
    )

    if not isinstance(
        raw_entities,
        list,
    ):
        raise ValueError(
            "Device has no exportable entities"
        )

    entities = []

    for raw_entity in raw_entities:
        entity = _sanitize_entity(
            raw_entity
        )

        if entity is None:
            raise ValueError(
                "Device contains an entity that cannot be safely exported"
            )

        entities.append(entity)

    if not entities:
        raise ValueError(
            "Device has no exportable entities"
        )

    required_dps = (
        _collect_required_dps(
            entities
        )
    )

    if not required_dps:
        raise ValueError(
            "Mapping does not reference any valid DPS"
        )

    observed_dps = (
        _parse_observed_dps(
            device_data
        )
    )

    if not observed_dps:
        raise ValueError(
            "No stored LAN DPS fingerprint is available; "
            "reconfigure the device before exporting"
        )

    missing_dps = (
        set(required_dps)
        - set(observed_dps)
    )

    if missing_dps:
        raise ValueError(
            "Mapping references DPS not present in "
            f"the stored LAN fingerprint: "
            f"{sorted(missing_dps)}"
        )

    category = _find_category(
        device_data,
        cloud_device,
    )

    match = {
        "product_id": product_id,
        "category": category,
        "required_dps":
            required_dps,
    }

    mapping_without_id = {
        "confidence": "experimental",
        "match": match,
        "entities": entities,
    }

    canonical = json.dumps(
        mapping_without_id,
        sort_keys=True,
        separators=(",", ":"),
    )

    digest = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()[:10]

    mapping_id = (
        f"{_safe_mapping_id_part(product_id)}-"
        f"{digest}"
    )

    mapping = {
        "id": mapping_id,
        **mapping_without_id,
    }

    # This object can be submitted to the community repository.
    # fingerprint is review metadata; runtime catalog loading only
    # consumes schema_version + mappings.
    return {
        "schema_version":
            CATALOG_SCHEMA_VERSION,
        "mappings": [
            mapping
        ],
        "fingerprint": {
            "observed_dps":
                observed_dps,
            "required_dps":
                required_dps,
            "protocol_version": str(
                device_data.get(
                    CONF_PROTOCOL_VERSION,
                    "",
                )
            ),
            "entity_count":
                len(entities),
        },
    }
