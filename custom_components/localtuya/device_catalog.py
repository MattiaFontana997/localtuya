"""Remote LocalTuya device mapping catalog."""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aiohttp import ClientError, ClientTimeout

from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession,
)
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

CATALOG_SCHEMA_VERSION = 1

CATALOG_URL = (
    "https://raw.githubusercontent.com/"
    "MattiaFontana997/localtuya-device-catalog/"
    "main/catalog.json"
)

REQUEST_TIMEOUT = ClientTimeout(total=10)

MAX_REMOTE_CATALOG_BYTES = 2 * 1024 * 1024
MAX_CATALOG_MAPPINGS = 2048
MAX_DP_ID = 65535
MAX_CONFIG_DEPTH = 12
MAX_CONFIG_NODES = 4096

BUILTIN_CATALOG_PATH = (
    Path(__file__).with_name(
        "builtin_catalog.json"
    )
)

CATALOG_STORAGE_VERSION = 1
CATALOG_STORAGE_KEY = "localtuya.device_catalog"

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

# These keys must never arrive from a remote device mapping.
# Catalog entries describe entity behaviour only, never account,
# device or network credentials.
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

# Remote mappings may explicitly override selected built-in
# configuration keys, but identity and user-facing naming must
# always remain under LocalTuya/local configuration control.
_PROTECTED_OVERRIDE_KEYS = {
    "id",
    "platform",
    "friendly_name",
}


@dataclass(frozen=True, slots=True)
class CatalogMatch:
    """A validated mapping returned by the remote catalog."""

    mapping_id: str
    product_id: str
    confidence: str
    required_dps: tuple[int, ...]
    entities: tuple[dict[str, Any], ...]
    source: str = "remote"


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


def _normalize_config_key(
    value: Any,
) -> str:
    """Normalize config keys to block separator/case bypasses."""
    return "".join(
        char
        for char
        in str(value).casefold()
        if char.isalnum()
    )


_FORBIDDEN_CONFIG_KEY_TOKENS = {
    _normalize_config_key(key)
    for key in _FORBIDDEN_CONFIG_KEYS
}

_PROTECTED_OVERRIDE_KEY_TOKENS = {
    _normalize_config_key(key)
    for key in _PROTECTED_OVERRIDE_KEYS
}


def _json_structure_safe(
    value: Any,
) -> bool:
    """Validate nesting and complexity of catalog config values."""
    stack = [
        (
            value,
            0,
        )
    ]
    nodes = 0

    while stack:
        current, depth = stack.pop()

        nodes += 1

        if (
            depth > MAX_CONFIG_DEPTH
            or nodes > MAX_CONFIG_NODES
        ):
            return False

        if isinstance(current, dict):
            for key, child in current.items():
                if not isinstance(key, str):
                    return False

                stack.append(
                    (
                        child,
                        depth + 1,
                    )
                )

        elif isinstance(current, list):
            for child in current:
                stack.append(
                    (
                        child,
                        depth + 1,
                    )
                )

        elif not isinstance(
            current,
            (
                str,
                int,
                float,
                bool,
                type(None),
            ),
        ):
            return False

    return True


def _contains_forbidden_keys(
    value: Any,
) -> bool:
    """Return whether a JSON value contains forbidden config keys."""
    stack = [value]

    while stack:
        current = stack.pop()

        if isinstance(current, dict):
            for key, child in current.items():
                normalized_key = (
                    _normalize_config_key(
                        key
                    )
                )

                if (
                    normalized_key
                    in _FORBIDDEN_CONFIG_KEY_TOKENS
                ):
                    return True

                stack.append(child)

        elif isinstance(current, list):
            stack.extend(current)

    return False

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

    if not _json_structure_safe(config):
        return None

    if _contains_forbidden_keys(config):
        return None

    raw_override_keys = entity.get(
        "override_keys",
        [],
    )

    if not isinstance(
        raw_override_keys,
        list,
    ):
        return None

    override_keys: list[str] = []

    for raw_key in raw_override_keys:
        if not isinstance(raw_key, str):
            return None

        key = raw_key.strip()
        normalized_key = (
            _normalize_config_key(
                key
            )
        )

        if (
            not key
            or normalized_key
            in _PROTECTED_OVERRIDE_KEY_TOKENS
            or normalized_key
            in _FORBIDDEN_CONFIG_KEY_TOKENS
            or key not in config
        ):
            return None

        if key not in override_keys:
            override_keys.append(key)

    config = copy.deepcopy(config)

    configured_platform = config.get(
        "platform"
    )

    if (
        configured_platform is not None
        and configured_platform != platform
    ):
        return None

    primary_dp = config.get("id")

    if isinstance(primary_dp, bool):
        return None

    try:
        primary_dp = int(primary_dp)
    except (TypeError, ValueError):
        return None

    if (
        primary_dp <= 0
        or primary_dp > MAX_DP_ID
    ):
        return None

    config["id"] = primary_dp
    config["platform"] = platform

    validated_entity = {
        "platform": platform,
        "config": config,
    }

    if override_keys:
        validated_entity[
            "override_keys"
        ] = override_keys

    return validated_entity


def validate_catalog(
    payload: Any,
) -> dict[str, Any]:
    """Validate remote catalog structure."""
    if not isinstance(payload, dict):
        raise ValueError(
            "Catalog root must be an object"
        )

    if (
        payload.get("schema_version")
        != CATALOG_SCHEMA_VERSION
    ):
        raise ValueError(
            "Unsupported catalog schema version"
        )

    mappings = payload.get(
        "mappings"
    )

    if not isinstance(
        mappings,
        list,
    ):
        raise ValueError(
            "Catalog mappings must be a list"
        )

    if (
        len(mappings)
        > MAX_CATALOG_MAPPINGS
    ):
        raise ValueError(
            "Catalog contains too many mappings"
        )

    validated = []
    seen_mapping_ids: set[str] = set()

    for raw_mapping in mappings:
        if not isinstance(
            raw_mapping,
            dict,
        ):
            continue

        mapping_id = raw_mapping.get(
            "id"
        )
        match = raw_mapping.get(
            "match"
        )
        entities = raw_mapping.get(
            "entities"
        )

        if (
            not isinstance(
                mapping_id,
                str,
            )
            or not mapping_id.strip()
            or not isinstance(
                match,
                dict,
            )
            or not isinstance(
                entities,
                list,
            )
        ):
            continue

        mapping_id = (
            mapping_id.strip()
        )

        if (
            mapping_id
            in seen_mapping_ids
        ):
            raise ValueError(
                "Duplicate catalog mapping ID: "
                f"{mapping_id}"
            )

        seen_mapping_ids.add(
            mapping_id
        )

        product_id = match.get(
            "product_id"
        )

        # Catalog mappings are product-specific.
        if (
            not isinstance(
                product_id,
                str,
            )
            or not product_id.strip()
        ):
            continue

        product_id = (
            product_id.strip()
        )

        category = match.get(
            "category"
        )

        if category is not None:
            if not isinstance(
                category,
                str,
            ):
                continue

            category = (
                category
                .strip()
                .lower()
            )

            if not category:
                category = None

        required_dps = match.get(
            "required_dps",
            [],
        )

        if not isinstance(
            required_dps,
            list,
        ):
            continue

        normalized_dps: list[int] = []
        valid_dps = True

        for dp in required_dps:
            if isinstance(
                dp,
                bool,
            ):
                valid_dps = False
                break

            try:
                dp_id = int(dp)
            except (
                TypeError,
                ValueError,
            ):
                valid_dps = False
                break

            if (
                dp_id <= 0
                or dp_id > MAX_DP_ID
            ):
                valid_dps = False
                break

            if (
                dp_id
                not in normalized_dps
            ):
                normalized_dps.append(
                    dp_id
                )

        if not valid_dps:
            continue

        validated_entities = []
        mapping_entities_valid = True

        for entity in entities:
            normalized = (
                _validate_entity(
                    entity
                )
            )

            # A product mapping is atomic:
            # one invalid entity invalidates
            # the complete mapping.
            if normalized is None:
                mapping_entities_valid = (
                    False
                )
                break

            primary_dp = (
                normalized[
                    "config"
                ]["id"]
            )

            if (
                primary_dp
                not in normalized_dps
            ):
                normalized_dps.append(
                    primary_dp
                )

            validated_entities.append(
                normalized
            )

        if (
            not mapping_entities_valid
            or not validated_entities
        ):
            continue

        raw_confidence = (
            raw_mapping.get(
                "confidence",
                "experimental",
            )
        )

        if not isinstance(
            raw_confidence,
            str,
        ):
            continue

        confidence = (
            raw_confidence
            .strip()
            .lower()
        )

        if confidence not in {
            "experimental",
            "verified",
            "community",
        }:
            continue

        validated.append(
            {
                "id": mapping_id,
                "match": {
                    "product_id":
                        product_id,
                    "category":
                        category,
                    "required_dps":
                        sorted(
                            normalized_dps
                        ),
                },
                "confidence":
                    confidence,
                "entities":
                    validated_entities,
            }
        )

    return {
        "schema_version":
            CATALOG_SCHEMA_VERSION,
        "mappings":
            validated,
    }


def _validate_runtime_catalog(
    payload: Any,
) -> dict[str, Any]:
    """Validate a cache or remote catalog without accepting a silent wipe."""
    validated = validate_catalog(
        payload
    )

    source_mappings = (
        payload.get("mappings")
        if isinstance(payload, dict)
        else None
    )

    # If the source claimed to contain mappings but every one
    # was rejected, treat the complete payload as corrupt.
    #
    # This prevents a malformed remote/cache catalog from
    # replacing known-good mappings with an empty catalog.
    if (
        isinstance(
            source_mappings,
            list,
        )
        and source_mappings
        and not validated["mappings"]
    ):
        raise ValueError(
            "Catalog contains no valid mappings"
        )

    return validated


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

    product_id = _device_product_id(
        device
    )

    if not product_id:
        return None

    category = _device_category(
        device
    )

    best_match = None
    best_score = -1

    for mapping in catalog.get(
        "mappings",
        [],
    ):
        match = mapping["match"]

        expected_product = match.get(
            "product_id"
        )

        if product_id != expected_product:
            continue

        expected_category = match.get(
            "category"
        )

        required_dps = set(
            match.get(
                "required_dps",
                [],
            )
        )

        if not required_dps.issubset(
            available_dps
        ):
            continue

        score = 100

        if expected_category:
            if (
                category
                and category
                != expected_category
            ):
                continue

            if (
                category
                == expected_category
            ):
                score += 10

        score += len(required_dps)

        if score <= best_score:
            continue

        best_score = score
        best_match = mapping

    if best_match is None:
        return None

    return CatalogMatch(
        mapping_id=best_match["id"],
        product_id=product_id,
        confidence=best_match[
            "confidence"
        ],
        required_dps=tuple(
            best_match["match"][
                "required_dps"
            ]
        ),
        entities=tuple(
            copy.deepcopy(entity)
            for entity
            in best_match["entities"]
        ),
        source=source,
    )


def load_builtin_catalog(
    path: Path = BUILTIN_CATALOG_PATH,
) -> dict[str, Any]:
    """Load the bundled physically verified catalog snapshot."""
    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        validated = validate_catalog(
            payload
        )

    except (
        OSError,
        ValueError,
    ) as ex:
        _LOGGER.error(
            "Unable to load bundled LocalTuya "
            "device catalog: %s",
            ex,
        )

        return {
            "schema_version":
                CATALOG_SCHEMA_VERSION,
            "mappings": [],
        }

    # Only physically verified mappings may ship
    # as an offline bundled snapshot.
    mappings = [
        mapping
        for mapping
        in validated["mappings"]
        if (
            mapping["confidence"]
            == "verified"
        )
    ]

    return {
        "schema_version":
            CATALOG_SCHEMA_VERSION,
        "mappings": mappings,
    }


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
        """Initialize catalog client."""
        self._hass = hass
        self._url = url

        # Loaded asynchronously during integration setup.
        # Never perform Path.read_text() from __init__, since
        # DeviceCatalog is constructed inside Home Assistant's
        # event loop.
        self._builtin_catalog = {
            "schema_version":
                CATALOG_SCHEMA_VERSION,
            "mappings": [],
        }

        self._session = (
            session
            if session is not None
            else async_get_clientsession(
                hass
            )
        )

        self._store = (
            store
            if store is not None
            else Store(
                hass,
                CATALOG_STORAGE_VERSION,
                CATALOG_STORAGE_KEY,
            )
        )

        self._catalog: dict[
            str,
            Any,
        ] | None = None

        self._etag: str | None = None

        self._cache_loaded = False

    async def async_load_builtin_catalog(
        self,
    ) -> bool:
        """Load the bundled catalog without blocking the HA event loop."""
        try:
            if self._hass is None:
                catalog = load_builtin_catalog()
            else:
                catalog = await (
                    self._hass.async_add_executor_job(
                        load_builtin_catalog
                    )
                )
        except Exception as ex:
            _LOGGER.error(
                "Unable to load bundled LocalTuya "
                "device catalog asynchronously: %s",
                ex,
            )
            return False

        self._builtin_catalog = catalog
        return True

    @property
    def catalog(
        self,
    ) -> dict[str, Any] | None:
        """Return currently loaded catalog."""
        return self._catalog

    @property
    def bundled_mapping_count(self) -> int:
        """Return number of bundled verified mappings."""
        return len(
            self._builtin_catalog.get(
                "mappings",
                [],
            )
        )

    @property
    def remote_mapping_count(self) -> int:
        """Return number of cached/remote mappings."""
        if self._catalog is None:
            return 0

        return len(
            self._catalog.get(
                "mappings",
                [],
            )
        )

    @property
    def mapping_count(self) -> int:
        """Return number of mappings in the preferred catalog."""
        if self._catalog is not None:
            return (
                self.remote_mapping_count
            )

        return (
            self.bundled_mapping_count
        )

    @property
    def cache_loaded(self) -> bool:
        """Return whether catalog was restored from persistent cache."""
        return self._cache_loaded

    async def async_load_cache(
        self,
    ) -> bool:
        """Restore last valid catalog from Home Assistant storage."""
        try:
            stored = (
                await self._store.async_load()
            )
        except Exception as ex:
            _LOGGER.debug(
                "Unable to load LocalTuya device catalog cache: %s",
                ex,
            )
            return False

        if not isinstance(stored, dict):
            return False

        # Never restore a cache created for a different
        # catalog endpoint.
        if stored.get("url") != self._url:
            _LOGGER.debug(
                "Ignoring LocalTuya device catalog "
                "cache from a different URL"
            )
            return False

        try:
            validated = _validate_runtime_catalog(
                stored.get("catalog")
            )
        except ValueError as ex:
            _LOGGER.debug(
                "Ignoring invalid cached LocalTuya catalog: %s",
                ex,
            )
            return False

        self._catalog = validated
        self._cache_loaded = True

        etag = stored.get(
            "etag"
        )

        if isinstance(etag, str):
            self._etag = etag

        _LOGGER.info(
            "Loaded cached LocalTuya device catalog with %s mappings",
            self.mapping_count,
        )

        return True

    async def _async_save_cache(
        self,
    ) -> bool:
        """Persist currently valid catalog."""
        if self._catalog is None:
            return False

        try:
            await self._store.async_save(
                {
                    "url": self._url,
                    "etag": self._etag,
                    "catalog":
                        self._catalog,
                }
            )
        except Exception as ex:
            _LOGGER.debug(
                "Unable to save LocalTuya device catalog cache: %s",
                ex,
            )
            return False

        return True

    async def async_refresh(
        self,
    ) -> bool:
        """Download and validate latest catalog.

        The current in-memory or cached catalog remains active
        whenever the remote refresh fails.
        """
        headers = {}

        if self._etag:
            headers[
                "If-None-Match"
            ] = self._etag

        try:
            async with self._session.get(
                self._url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status == 304:
                    return (
                        self._catalog
                        is not None
                    )

                if response.status != 200:
                    _LOGGER.debug(
                        "Remote device catalog returned HTTP %s",
                        response.status,
                    )
                    return False

                content_length = getattr(
                    response,
                    "content_length",
                    None,
                )

                if (
                    isinstance(
                        content_length,
                        int,
                    )
                    and content_length
                    > MAX_REMOTE_CATALOG_BYTES
                ):
                    _LOGGER.warning(
                        "Remote LocalTuya device catalog "
                        "exceeds the maximum allowed size"
                    )
                    return False

                payload = await response.json(
                    content_type=None
                )

                # Also enforce the limit after parsing so
                # responses without Content-Length cannot
                # silently persist an oversized catalog.
                encoded_size = len(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        separators=(
                            ",",
                            ":",
                        ),
                    ).encode(
                        "utf-8"
                    )
                )

                if (
                    encoded_size
                    > MAX_REMOTE_CATALOG_BYTES
                ):
                    _LOGGER.warning(
                        "Remote LocalTuya device catalog "
                        "exceeds the maximum allowed size"
                    )
                    return False

                validated = _validate_runtime_catalog(
                    payload
                )

                # Only replace the current catalog after the
                # entire remote payload has validated.
                self._catalog = validated

                etag = response.headers.get(
                    "ETag"
                )

                self._etag = (
                    etag
                    if isinstance(etag, str)
                    else None
                )

                await self._async_save_cache()

                _LOGGER.info(
                    "Loaded remote LocalTuya device catalog with %s mappings",
                    self.mapping_count,
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
        """Return the safest compatible product-specific mapping."""
        remote_match = (
            match_catalog_mapping(
                self._catalog,
                device,
                available_dps,
                source="remote",
            )
        )

        bundled_match = (
            match_catalog_mapping(
                self._builtin_catalog,
                device,
                available_dps,
                source="bundled",
            )
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

        # Never allow newer but less-trusted remote data
        # to replace a physically verified bundled mapping.
        if (
            confidence_rank.get(
                remote_match.confidence,
                0,
            )
            < confidence_rank.get(
                bundled_match.confidence,
                0,
            )
        ):
            return bundled_match

        # Equal-or-higher trust means the remote mapping
        # represents the preferred newer knowledge.
        return remote_match
