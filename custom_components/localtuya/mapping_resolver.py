"""Unified LocalTuya entity mapping resolver."""

from __future__ import annotations

import copy
import logging
from typing import Any

from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    CONF_ID,
    CONF_PLATFORM,
)

from .device_mapper import (
    EntityCandidate,
    MappingConfidence,
    MappingSource,
    MappingTrust,
    build_entity_candidates,
)

_LOGGER = logging.getLogger(__name__)

_TRUSTED_CATALOG_CONFIDENCE = {
    "verified",
    "community",
}


def _catalog_trust(
    confidence: str,
) -> MappingTrust:
    """Convert catalog confidence into a conservative UI trust value."""
    try:
        return MappingTrust(confidence)
    except ValueError:
        # Runtime validation should normally make this unreachable. Unknown
        # catalog trust is treated conservatively rather than promoted.
        return MappingTrust.EXPERIMENTAL


def _device_label(mapper_device: dict[str, Any]) -> str:
    """Return a stable human-readable device label for generated entity names."""
    return str(
        mapper_device.get("name")
        or mapper_device.get("product_name")
        or mapper_device.get("productName")
        or "Tuya Device"
    )


def _ensure_friendly_name(
    config: dict[str, Any],
    mapper_device: dict[str, Any],
    platform: str,
    primary_dp: int,
    generic: EntityCandidate | None = None,
) -> None:
    """Keep a catalog name, otherwise reuse generic naming before generating one."""
    if config.get(CONF_FRIENDLY_NAME):
        return

    if generic is not None and generic.config.get(CONF_FRIENDLY_NAME):
        config[CONF_FRIENDLY_NAME] = generic.config[CONF_FRIENDLY_NAME]
        return

    config[CONF_FRIENDLY_NAME] = (
        f"{_device_label(mapper_device)} "
        f"{platform.replace('_', ' ').title()} "
        f"DP {primary_dp}"
    )


def _matching_generic_candidate(
    candidates: list[EntityCandidate],
    platform: str,
    primary_dp: int,
) -> EntityCandidate | None:
    """Return the generic candidate representing the same entity, if any."""
    return next(
        (
            candidate
            for candidate in candidates
            if (
                candidate.platform == platform
                and candidate.primary_dp == primary_dp
            )
        ),
        None,
    )


def _merge_references(
    catalog_refs: list[int],
    generic: EntityCandidate | None,
) -> tuple[int, ...]:
    """Merge catalog and generic DP references without losing LAN validation."""
    refs = list(catalog_refs)
    if generic is not None:
        for dp_id in generic.referenced_dps or (generic.primary_dp,):
            if dp_id not in refs:
                refs.append(dp_id)
    return tuple(refs)


def _merge_codes(
    catalog_marker: str,
    generic: EntityCandidate | None,
) -> tuple[str, ...]:
    """Merge mapper provenance while retaining the catalog marker."""
    codes = list(generic.matched_codes) if generic is not None else []
    if catalog_marker not in codes:
        codes.append(catalog_marker)
    return tuple(codes)


def _trusted_catalog_candidate(
    catalog_config: dict[str, Any],
    *,
    platform: str,
    primary_dp: int,
    catalog_refs: list[int],
    catalog_marker: str,
    catalog_match,
    mapper_device: dict[str, Any],
    generic: EntityCandidate | None,
) -> EntityCandidate:
    """Build a catalog-authoritative candidate with generic fill-only enrichment."""
    # A verified/community catalog mapping is the canonical device mapping.
    # Start from catalog data and only use generic knowledge to fill fields the
    # catalog does not define. This is intentionally the reverse of the legacy
    # merge order: generic inference must never replace product-specific
    # catalog semantics on first onboarding.
    merged_config = copy.deepcopy(catalog_config)

    if generic is not None:
        for config_key, config_value in generic.config.items():
            if config_key in {CONF_ID, CONF_PLATFORM, CONF_FRIENDLY_NAME}:
                continue
            merged_config.setdefault(config_key, config_value)

    merged_config[CONF_ID] = primary_dp
    merged_config[CONF_PLATFORM] = platform
    _ensure_friendly_name(
        merged_config,
        mapper_device,
        platform,
        primary_dp,
        generic,
    )

    return EntityCandidate(
        platform=platform,
        primary_dp=primary_dp,
        confidence=MappingConfidence.HIGH,
        config=merged_config,
        matched_codes=_merge_codes(catalog_marker, generic),
        referenced_dps=_merge_references(catalog_refs, generic),
        source=MappingSource.CATALOG,
        trust=_catalog_trust(catalog_match.confidence),
    )


def _merge_catalog_match(
    candidates: list[EntityCandidate],
    catalog_match,
    mapper_device: dict[str, Any],
    detected_ids: set[int],
) -> list[EntityCandidate]:
    """Merge one product-specific catalog mapping into candidates.

    Verified/community matches are authoritative for the entity set and for all
    fields explicitly present in the catalog. Generic mapping is used only to
    fill missing fields on the same catalog entity. Experimental matches retain
    the conservative legacy behavior and never silently replace generic values
    unless an explicit ``override_keys`` declaration requests reviewable
    replacement.
    """
    trusted_catalog = catalog_match.confidence in _TRUSTED_CATALOG_CONFIDENCE
    generic_candidates = list(candidates)
    result: list[EntityCandidate] = [] if trusted_catalog else list(candidates)

    _LOGGER.info(
        "Matched %s LocalTuya catalog mapping %s for product %s",
        getattr(catalog_match, "source", "remote"),
        catalog_match.mapping_id,
        catalog_match.product_id,
    )

    for catalog_entity in catalog_match.entities:
        config = copy.deepcopy(catalog_entity["config"])
        override_keys = set(catalog_entity.get("override_keys", ()))
        platform = catalog_entity["platform"]

        try:
            primary_dp = int(config.get(CONF_ID))
        except (TypeError, ValueError):
            continue

        # Primary entity DP must always exist on LAN.
        if primary_dp not in detected_ids:
            continue

        catalog_marker = f"catalog:{catalog_match.mapping_id}"
        catalog_refs = list(catalog_match.required_dps)
        if primary_dp not in catalog_refs:
            catalog_refs.append(primary_dp)

        generic = _matching_generic_candidate(
            generic_candidates,
            platform,
            primary_dp,
        )

        if trusted_catalog:
            result.append(
                _trusted_catalog_candidate(
                    config,
                    platform=platform,
                    primary_dp=primary_dp,
                    catalog_refs=catalog_refs,
                    catalog_marker=catalog_marker,
                    catalog_match=catalog_match,
                    mapper_device=mapper_device,
                    generic=generic,
                )
            )
            continue

        # Experimental catalog mappings remain conservative. Generic inference
        # stays authoritative unless the catalog explicitly names an override.
        config[CONF_ID] = primary_dp
        config[CONF_PLATFORM] = platform
        _ensure_friendly_name(
            config,
            mapper_device,
            platform,
            primary_dp,
            generic,
        )

        existing_index = next(
            (
                index
                for index, candidate in enumerate(result)
                if (
                    candidate.platform == platform
                    and candidate.primary_dp == primary_dp
                )
            ),
            None,
        )

        if existing_index is not None:
            existing = result[existing_index]
            merged_config = dict(existing.config)
            override_applied = False

            for config_key, config_value in config.items():
                if config_key in {
                    CONF_ID,
                    CONF_PLATFORM,
                    CONF_FRIENDLY_NAME,
                }:
                    continue

                if (
                    config_key in override_keys
                    and config_key in merged_config
                ):
                    if merged_config[config_key] != config_value:
                        merged_config[config_key] = config_value
                        override_applied = True
                    continue

                merged_config.setdefault(config_key, config_value)

            referenced_dps = list(
                existing.referenced_dps or (existing.primary_dp,)
            )
            for dp_id in catalog_refs:
                if dp_id not in referenced_dps:
                    referenced_dps.append(dp_id)

            matched_codes = list(existing.matched_codes)
            if catalog_marker not in matched_codes:
                matched_codes.append(catalog_marker)

            if override_applied:
                merged_confidence = MappingConfidence.MEDIUM
                merged_source = MappingSource.CATALOG
                merged_trust = MappingTrust.EXPERIMENTAL
            else:
                merged_confidence = existing.confidence
                merged_source = existing.source
                merged_trust = existing.trust

            result[existing_index] = EntityCandidate(
                platform=existing.platform,
                primary_dp=existing.primary_dp,
                confidence=merged_confidence,
                config=merged_config,
                matched_codes=tuple(matched_codes),
                referenced_dps=tuple(referenced_dps),
                source=merged_source,
                trust=merged_trust,
            )
            continue

        # Catalog-only experimental entities are reviewable, never automatic.
        result.append(
            EntityCandidate(
                platform=platform,
                primary_dp=primary_dp,
                confidence=MappingConfidence.MEDIUM,
                config=config,
                matched_codes=(catalog_marker,),
                referenced_dps=tuple(catalog_refs),
                source=MappingSource.CATALOG,
                trust=MappingTrust.EXPERIMENTAL,
            )
        )

    return result


def resolve_entity_candidates(
    mapper_device: dict[str, Any],
    specification: dict[str, Any] | None,
    detected_ids: set[int],
    *,
    catalog_client=None,
) -> list[EntityCandidate]:
    """Resolve all LocalTuya mapping sources into EntityCandidate objects."""
    candidates = build_entity_candidates(
        mapper_device,
        specification or {},
        available_dps=detected_ids,
    )

    if catalog_client is not None:
        catalog_match = catalog_client.match(
            mapper_device,
            detected_ids,
        )
        if catalog_match is not None:
            candidates = _merge_catalog_match(
                candidates,
                catalog_match,
                mapper_device,
                detected_ids,
            )

    accepted: list[EntityCandidate] = []

    for candidate in candidates:
        if candidate.confidence == MappingConfidence.LOW:
            continue

        referenced_dps = candidate.referenced_dps or (candidate.primary_dp,)

        # LAN remains authoritative for every source: generic metadata, bundled
        # catalog and remote catalog. Catalog authority never bypasses observed
        # local datapoint validation.
        if not set(referenced_dps).issubset(detected_ids):
            _LOGGER.debug(
                "Ignoring mapping candidate %s DP %s: referenced DPS %s "
                "not all detected over LAN",
                candidate.platform,
                candidate.primary_dp,
                referenced_dps,
            )
            continue

        accepted.append(candidate)

    return sorted(
        accepted,
        key=lambda candidate: (
            candidate.platform,
            candidate.primary_dp,
        ),
    )
