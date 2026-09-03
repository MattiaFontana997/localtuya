"""Remote LocalTuya device mapping catalog."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError, ClientTimeout

from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession,
)

_LOGGER = logging.getLogger(__name__)

CATALOG_SCHEMA_VERSION = 1

CATALOG_URL = (
    "https://raw.githubusercontent.com/"
    "MattiaFontana997/localtuya-device-catalog/"
    "main/catalog.json"
)

REQUEST_TIMEOUT = ClientTimeout(total=10)

SUPPORTED_PLATFORMS = {
    "binary_sensor",
    "climate",
    "cover",
    "fan",
    "light",
    "number",
    "select",
    "sensor",
    "switch",
    "vacuum",
}


@dataclass(frozen=True, slots=True)
class CatalogMatch:
    """A validated mapping returned by the remote catalog."""

    mapping_id: str
    product_id: str
    confidence: str
    entities: tuple[dict[str, Any], ...]


def _device_product_id(
    device: dict[str, Any],
) -> str | None:
    """Extract product ID/key from Tuya metadata."""
    for key in (
        "product_id",
        "productId",
        "product_key",
        "productKey",
    ):
        value = device.get(key)

        if value:
            return str(value).strip()

    return None


def _device_category(
    device: dict[str, Any],
) -> str:
    """Extract Tuya category."""
    value = device.get("category")

    if not value:
        return ""

    return str(value).strip().lower()


def _validate_entity(
    entity: Any,
) -> dict[str, Any] | None:
    """Validate one catalog entity without allowing arbitrary code."""
    if not isinstance(entity, dict):
        return None

    platform = entity.get("platform")

    if platform not in SUPPORTED_PLATFORMS:
        return None

    config = entity.get("config")

    if not isinstance(config, dict):
        return None

    # Only JSON-compatible configuration is allowed.
    # No executable expressions or dynamically imported code.
    return {
        "platform": platform,
        "config": copy.deepcopy(config),
    }


def validate_catalog(
    payload: Any,
) -> dict[str, Any]:
    """Validate remote catalog structure."""
    if not isinstance(payload, dict):
        raise ValueError("Catalog root must be an object")

    if payload.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported catalog schema version"
        )

    mappings = payload.get("mappings")

    if not isinstance(mappings, list):
        raise ValueError("Catalog mappings must be a list")

    validated = []

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

        product_id = match.get("product_id")
        category = match.get("category")
        required_dps = match.get("required_dps", [])

        if product_id is not None:
            product_id = str(product_id).strip()

        if category is not None:
            category = str(category).strip().lower()

        if not isinstance(required_dps, list):
            continue

        normalized_dps: list[int] = []

        valid_dps = True

        for dp in required_dps:
            try:
                dp_id = int(dp)
            except (TypeError, ValueError):
                valid_dps = False
                break

            if dp_id <= 0:
                valid_dps = False
                break

            normalized_dps.append(dp_id)

        if not valid_dps:
            continue

        validated_entities = []

        for entity in entities:
            normalized = _validate_entity(entity)

            if normalized is not None:
                validated_entities.append(normalized)

        if not validated_entities:
            continue

        confidence = str(
            raw_mapping.get(
                "confidence",
                "experimental",
            )
        ).strip().lower()

        if confidence not in {
            "experimental",
            "verified",
            "community",
        }:
            confidence = "experimental"

        validated.append(
            {
                "id": mapping_id.strip(),
                "match": {
                    "product_id": product_id,
                    "category": category,
                    "required_dps": normalized_dps,
                },
                "confidence": confidence,
                "entities": validated_entities,
            }
        )

    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "mappings": validated,
    }


def match_catalog_mapping(
    catalog: dict[str, Any] | None,
    device: dict[str, Any],
    available_dps: set[int],
) -> CatalogMatch | None:
    """Find the best compatible catalog mapping."""
    if not catalog:
        return None

    product_id = _device_product_id(device)
    category = _device_category(device)

    best_match = None
    best_score = -1

    for mapping in catalog.get("mappings", []):
        match = mapping["match"]

        expected_product = match.get("product_id")
        expected_category = match.get("category")
        required_dps = set(
            match.get("required_dps", [])
        )

        score = 0

        if expected_product:
            if product_id != expected_product:
                continue

            score += 100

        if expected_category:
            if category != expected_category:
                continue

            score += 10

        if not required_dps.issubset(
            available_dps
        ):
            continue

        score += len(required_dps)

        if score <= best_score:
            continue

        best_score = score
        best_match = mapping

    if best_match is None:
        return None

    resolved_product_id = (
        _device_product_id(device) or ""
    )

    return CatalogMatch(
        mapping_id=best_match["id"],
        product_id=resolved_product_id,
        confidence=best_match["confidence"],
        entities=tuple(
            copy.deepcopy(
                entity
            )
            for entity in best_match["entities"]
        ),
    )


class DeviceCatalog:
    """Remote LocalTuya device catalog with safe in-memory fallback."""

    def __init__(
        self,
        hass,
        *,
        url: str = CATALOG_URL,
    ) -> None:
        """Initialize catalog client."""
        self._hass = hass
        self._url = url
        self._session = async_get_clientsession(
            hass
        )

        self._catalog: dict[
            str,
            Any,
        ] | None = None

        self._etag: str | None = None

    @property
    def catalog(
        self,
    ) -> dict[str, Any] | None:
        """Return currently loaded catalog."""
        return self._catalog

    async def async_refresh(
        self,
    ) -> bool:
        """Download and validate latest catalog.

        Existing valid catalog remains active if refresh fails.
        """
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
                    return True

                if response.status != 200:
                    _LOGGER.debug(
                        "Remote device catalog returned HTTP %s",
                        response.status,
                    )
                    return False

                payload = await response.json(
                    content_type=None
                )

                validated = validate_catalog(
                    payload
                )

                self._catalog = validated

                self._etag = response.headers.get(
                    "ETag"
                )

                _LOGGER.info(
                    "Loaded LocalTuya device catalog with %s mappings",
                    len(
                        validated[
                            "mappings"
                        ]
                    ),
                )

                return True

        except (
            ClientError,
            TimeoutError,
            ValueError,
        ) as ex:
            _LOGGER.debug(
                "Unable to refresh LocalTuya device catalog: %s",
                ex,
            )

            return False

    def match(
        self,
        device: dict[str, Any],
        available_dps: set[int],
    ) -> CatalogMatch | None:
        """Match a device against current catalog."""
        return match_catalog_mapping(
            self._catalog,
            device,
            available_dps,
        )
