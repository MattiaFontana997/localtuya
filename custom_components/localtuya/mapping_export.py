"""Sanitized LocalTuya community mapping export."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import quote, urlencode

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
# Normalized sensitive keys. Separators and case are removed
# before comparison, so variants such as localKey, local-key,
# LOCAL_KEY and clientSecret are treated identically.
_SENSITIVE_ENTITY_KEYS = {
    "localkey",
    "deviceid",
    "host",
    "ip",
    "gwid",
    "clientid",
    "clientsecret",
    "userid",
    "username",
    "region",
    "ownerid",
    "uuid",
    "uid",
    "mac",
    "latitude",
    "longitude",
    "lat",
    "lon",
    "friendlyname",
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
            normalized_key = re.sub(
                r"[^a-z0-9]+",
                "",
                str(key)
                .strip()
                .lower(),
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


def _mapping_entity_identity(
    entity: Any,
) -> tuple[str, int] | None:
    """Return platform/DP identity for an exported or baseline entity."""
    if not isinstance(
        entity,
        dict,
    ):
        return None

    platform = entity.get(
        "platform"
    )

    config = entity.get(
        "config"
    )

    if (
        not isinstance(
            platform,
            str,
        )
        or not isinstance(
            config,
            dict,
        )
    ):
        return None

    primary_dp = config.get(
        CONF_ID
    )

    if isinstance(
        primary_dp,
        bool,
    ):
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

    return (
        platform,
        primary_dp,
    )


def _apply_baseline_override_keys(
    entities: list[dict[str, Any]],
    baseline_entities: list[dict[str, Any]]
    | None,
) -> None:
    """Mark only settings that must replace generic knowledge."""
    if not isinstance(
        baseline_entities,
        list,
    ):
        return

    baselines = {}

    for entity in baseline_entities:
        identity = (
            _mapping_entity_identity(
                entity
            )
        )

        if identity is None:
            continue

        config = entity.get(
            "config"
        )

        if isinstance(
            config,
            dict,
        ):
            baselines[
                identity
            ] = config

    protected_keys = {
        CONF_ID,
        CONF_PLATFORM,
        CONF_FRIENDLY_NAME,
    }

    for entity in entities:
        identity = (
            _mapping_entity_identity(
                entity
            )
        )

        if identity is None:
            continue

        baseline = baselines.get(
            identity
        )

        if not isinstance(
            baseline,
            dict,
        ):
            continue

        config = entity[
            "config"
        ]

        override_keys = []

        for (
            key,
            value,
        ) in config.items():
            if key in protected_keys:
                continue

            # A catalog override is necessary only
            # when generic mapping already owns the
            # same key with a different value.
            if (
                key in baseline
                and baseline[key]
                != value
            ):
                override_keys.append(
                    key
                )

        if override_keys:
            entity[
                "override_keys"
            ] = sorted(
                override_keys
            )



def build_mapping_submission(
    device_data: dict[str, Any],
    *,
    cloud_device: dict[str, Any] | None = None,
    baseline_entities: list[dict[str, Any]]
    | None = None,
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

    _apply_baseline_override_keys(
        entities,
        baseline_entities,
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


COMMUNITY_CATALOG_REPOSITORY_URL = (
    "https://github.com/"
    "MattiaFontana997/"
    "localtuya-device-catalog"
)

COMMUNITY_CATALOG_NEW_SUBMISSION_URL = (
    f"{COMMUNITY_CATALOG_REPOSITORY_URL}"
    "/new/main/submissions"
)

# Keep the generated GitHub URL comfortably below common
# browser/proxy limits. Larger submissions fall back to
# filename-only prefill while the JSON remains available
# in the LocalTuya UI for manual copy.
MAX_GITHUB_PREFILL_URL_LENGTH = 7500


def _build_github_submission_url(
    suggested_filename: str,
    submission_json: str,
) -> str:
    """Build GitHub new-file URL with safe content prefill."""
    full_query = urlencode(
        [
            (
                "filename",
                suggested_filename,
            ),
            (
                "value",
                submission_json,
            ),
        ],
        quote_via=quote,
    )

    full_url = (
        f"{COMMUNITY_CATALOG_NEW_SUBMISSION_URL}"
        f"?{full_query}"
    )

    if (
        len(full_url)
        <= MAX_GITHUB_PREFILL_URL_LENGTH
    ):
        return full_url

    filename_query = urlencode(
        [
            (
                "filename",
                suggested_filename,
            ),
        ],
        quote_via=quote,
    )

    return (
        f"{COMMUNITY_CATALOG_NEW_SUBMISSION_URL}"
        f"?{filename_query}"
    )


def build_mapping_contribution_package(
    device_data: dict[str, Any],
    *,
    cloud_device: dict[str, Any] | None = None,
    baseline_entities: list[dict[str, Any]]
    | None = None,
) -> dict[str, Any]:
    """Build a privacy-safe package for a community contribution.

    This function never uploads anything. It prepares the sanitized
    submission, a human-readable preview, the suggested filename and
    navigation links for the public device catalog.
    """
    submission = build_mapping_submission(
        device_data,
        cloud_device=cloud_device,
        baseline_entities=baseline_entities,
    )

    mapping = submission[
        "mappings"
    ][0]

    match = mapping[
        "match"
    ]

    fingerprint = submission[
        "fingerprint"
    ]

    mapping_id = str(
        mapping["id"]
    )

    preview = {
        "mapping_id":
            mapping_id,
        "product_id":
            match.get(
                "product_id"
            ),
        "category":
            match.get(
                "category"
            ),
        "confidence":
            mapping.get(
                "confidence"
            ),
        "entity_count":
            fingerprint.get(
                "entity_count",
                0,
            ),
        "observed_dps":
            list(
                fingerprint.get(
                    "observed_dps",
                    [],
                )
            ),
        "required_dps":
            list(
                fingerprint.get(
                    "required_dps",
                    [],
                )
            ),
        "protocol_version":
            fingerprint.get(
                "protocol_version",
                "",
            ),
    }

    submission_json = json.dumps(
        submission,
        indent=2,
        ensure_ascii=False,
    )

    suggested_filename = (
        f"{mapping_id}.json"
    )

    new_submission_url = (
        _build_github_submission_url(
            suggested_filename,
            submission_json,
        )
    )

    return {
        "suggested_filename":
            suggested_filename,
        "repository_url":
            COMMUNITY_CATALOG_REPOSITORY_URL,
        "new_submission_url":
            new_submission_url,
        "preview":
            preview,
        "privacy": {
            "automatic_upload":
                False,
            "contains_local_key":
                False,
            "contains_device_id":
                False,
            "contains_ip_address":
                False,
            "contains_cloud_credentials":
                False,
            "contains_friendly_names":
                False,
        },
        "submission":
            submission,
        "submission_json":
            submission_json,
    }
