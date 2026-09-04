"""Diagnostics support for LocalTuya."""

from __future__ import annotations

import copy
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_FRIENDLY_NAME,
    CONF_HOST,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.redact import async_redact_data

from .const import (
    CONF_DPS_STRINGS,
    CONF_LOCAL_KEY,
    CONF_PRODUCT_KEY,
    CONF_USER_ID,
    DATA_CLOUD,
    DATA_DEVICE_CATALOG,
    DATA_DISCOVERY,
    DOMAIN,
)
from .mapping_resolver import (
    resolve_entity_candidates,
)

CLOUD_DEVICES = "cloud_devices"
DEVICE_CONFIG = "device_config"
DEVICE_CLOUD_INFO = "device_cloud_info"
MAPPING_DIAGNOSTICS = "mapping"

TO_REDACT = {
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
    CONF_USER_ID,
    CONF_LOCAL_KEY,
    CONF_HOST,
}

# These keys are sensitive only in Tuya Cloud device metadata.
# Do NOT add "id" to TO_REDACT globally: LocalTuya entity
# configurations legitimately use "id" for the datapoint ID.
CLOUD_DEVICE_TO_REDACT = {
    "id",
    "uuid",
    "uid",
    "ip",
    "device_id",
    "deviceId",
    "gwId",
    "gateway_id",
    "gatewayId",
    "mac",
    "owner_id",
    "ownerId",
    "local_key",
    "localKey",
    "latitude",
    "longitude",
    "lat",
    "lon",
}


def _privacy_safe_cloud_device(
    device_data,
) -> dict[str, Any]:
    """Return Cloud device metadata with identifiers removed."""
    if not isinstance(
        device_data,
        dict,
    ):
        return {}

    return async_redact_data(
        copy.deepcopy(
            device_data
        ),
        CLOUD_DEVICE_TO_REDACT,
    )


def _diagnostic_dp_ids(
    dps_values,
) -> list[int]:
    """Extract sorted datapoint IDs without exposing their values."""
    result: set[int] = set()

    for value in dps_values or ():
        try:
            dp_id = int(
                str(value)
                .split(" ", 1)[0]
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if dp_id > 0:
            result.add(
                dp_id
            )

    return sorted(
        result
    )


def _catalog_mapping_id(
    matched_codes,
) -> str | None:
    """Extract catalog mapping ID from resolver trace markers."""
    for raw_code in matched_codes or ():
        if not isinstance(
            raw_code,
            str,
        ):
            continue

        prefix = "catalog:"

        if not raw_code.startswith(
            prefix
        ):
            continue

        mapping_id = raw_code[
            len(prefix):
        ].strip()

        if mapping_id:
            return mapping_id

    return None


def build_mapping_diagnostics(
    dps_values,
    candidates,
) -> dict[str, Any]:
    """Build privacy-safe diagnostics for resolved mapping candidates."""
    result = {
        "observed_dps":
            _diagnostic_dp_ids(
                dps_values
            ),
        "candidates": [],
    }

    for candidate in candidates or ():
        source = getattr(
            candidate,
            "source",
            None,
        )

        trust = getattr(
            candidate,
            "trust",
            None,
        )

        confidence = getattr(
            candidate,
            "confidence",
            None,
        )

        matched_codes = tuple(
            getattr(
                candidate,
                "matched_codes",
                (),
            )
            or ()
        )

        referenced_dps = []

        for raw_dp in (
            getattr(
                candidate,
                "referenced_dps",
                (),
            )
            or ()
        ):
            if isinstance(
                raw_dp,
                bool,
            ):
                continue

            try:
                dp_id = int(
                    raw_dp
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            if (
                dp_id > 0
                and dp_id
                not in referenced_dps
            ):
                referenced_dps.append(
                    dp_id
                )

        result[
            "candidates"
        ].append(
            {
                "platform":
                    getattr(
                        candidate,
                        "platform",
                        None,
                    ),
                "primary_dp":
                    getattr(
                        candidate,
                        "primary_dp",
                        None,
                    ),
                "source":
                    (
                        source.value
                        if hasattr(
                            source,
                            "value",
                        )
                        else source
                    ),
                "trust":
                    (
                        trust.value
                        if hasattr(
                            trust,
                            "value",
                        )
                        else trust
                    ),
                "confidence":
                    (
                        confidence.value
                        if hasattr(
                            confidence,
                            "value",
                        )
                        else confidence
                    ),
                "catalog_mapping_id":
                    _catalog_mapping_id(
                        matched_codes
                    ),
                "referenced_dps":
                    sorted(
                        referenced_dps
                    ),
                "matched_codes": [
                    code
                    for code
                    in matched_codes
                    if isinstance(
                        code,
                        str,
                    )
                ],
            }
        )

    return result


async def _async_device_mapping_diagnostics(
    hass: HomeAssistant,
    device_id: str,
    device_config: dict[str, Any],
) -> dict[str, Any]:
    """Resolve privacy-safe mapping diagnostics for one configured device."""
    dps_values = device_config.get(
        CONF_DPS_STRINGS,
        (),
    )

    detected_ids = set(
        _diagnostic_dp_ids(
            dps_values
        )
    )

    domain_data = hass.data.get(
        DOMAIN,
        {},
    )

    discovered_device = {}

    discovery = domain_data.get(
        DATA_DISCOVERY
    )

    discovery_devices = getattr(
        discovery,
        "devices",
        {},
    )

    if isinstance(
        discovery_devices,
        dict,
    ):
        candidate = (
            discovery_devices.get(
                device_id
            )
        )

        if isinstance(
            candidate,
            dict,
        ):
            discovered_device = candidate

    cloud_device = {}
    specification = {}

    cloud_api = domain_data.get(
        DATA_CLOUD
    )

    if cloud_api is not None:
        device_list = getattr(
            cloud_api,
            "device_list",
            {},
        )

        if isinstance(
            device_list,
            dict,
        ):
            candidate = (
                device_list.get(
                    device_id
                )
            )

            if isinstance(
                candidate,
                dict,
            ):
                cloud_device = candidate

        # Prefer already cached specification metadata.
        cached_specifications = getattr(
            cloud_api,
            "device_specifications",
            {},
        )

        if isinstance(
            cached_specifications,
            dict,
        ):
            candidate = (
                cached_specifications.get(
                    device_id
                )
            )

            if isinstance(
                candidate,
                dict,
            ):
                specification = candidate

        # If the device is known to Cloud but its specification
        # is not cached yet, diagnostics may request it. Failure
        # must never prevent local/catalog diagnostics.
        if (
            cloud_device
            and not specification
        ):
            get_specification = getattr(
                cloud_api,
                "async_get_device_specification",
                None,
            )

            if callable(
                get_specification
            ):
                try:
                    (
                        result,
                        cloud_specification,
                    ) = await get_specification(
                        device_id
                    )

                    if (
                        result == "ok"
                        and isinstance(
                            cloud_specification,
                            dict,
                        )
                    ):
                        specification = (
                            cloud_specification
                        )

                except Exception:
                    # Diagnostics must remain available even if
                    # Tuya Cloud is offline or authentication has
                    # expired.
                    pass

    mapper_device = {
        **discovered_device,
        **cloud_device,
    }

    product_key = device_config.get(
        CONF_PRODUCT_KEY
    )

    if (
        product_key
        and not any(
            mapper_device.get(key)
            for key in (
                "product_id",
                "productId",
                "product_key",
                "productKey",
            )
        )
    ):
        mapper_device[
            "product_key"
        ] = product_key

    friendly_name = device_config.get(
        CONF_FRIENDLY_NAME
    )

    if friendly_name:
        mapper_device[
            "name"
        ] = friendly_name

    candidates = (
        resolve_entity_candidates(
            mapper_device,
            specification,
            detected_ids,
            catalog_client=(
                domain_data.get(
                    DATA_DEVICE_CATALOG
                )
            ),
        )
    )

    return build_mapping_diagnostics(
        dps_values,
        candidates,
    )


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    tuya_api = hass.data[DOMAIN][DATA_CLOUD]

    data = copy.deepcopy(dict(entry.data))
    data[CLOUD_DEVICES] = copy.deepcopy(tuya_api.device_list)

    return async_redact_data(data, TO_REDACT)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    dev_id = list(device.identifiers)[0][1].split("_")[-1]

    device_config = copy.deepcopy(
        entry.data[
            CONF_DEVICES
        ][dev_id]
    )

    data: dict[str, Any] = {
        DEVICE_CONFIG:
            device_config,
    }

    try:
        data[
            MAPPING_DIAGNOSTICS
        ] = await (
            _async_device_mapping_diagnostics(
                hass,
                dev_id,
                device_config,
            )
        )

    except Exception as ex:
        # Mapping diagnostics are supplementary. A resolver
        # failure must never prevent the user from downloading
        # the ordinary LocalTuya diagnostics.
        fallback = (
            build_mapping_diagnostics(
                device_config.get(
                    CONF_DPS_STRINGS,
                    (),
                ),
                (),
            )
        )

        # Expose only the exception class, never the message:
        # exception text could theoretically contain device,
        # network, or authentication information.
        fallback[
            "resolver_error"
        ] = type(ex).__name__

        data[
            MAPPING_DIAGNOSTICS
        ] = fallback

    tuya_api = hass.data[DOMAIN][DATA_CLOUD]

    if dev_id in tuya_api.device_list:
        data[
            DEVICE_CLOUD_INFO
        ] = _privacy_safe_cloud_device(
            tuya_api.device_list[
                dev_id
            ]
        )

    return async_redact_data(
        data,
        TO_REDACT,
    )
