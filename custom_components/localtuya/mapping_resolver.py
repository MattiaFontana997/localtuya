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
    build_entity_candidates,
)

_LOGGER = logging.getLogger(__name__)


def _merge_catalog_match(
    candidates: list[EntityCandidate],
    catalog_match,
    mapper_device: dict[str, Any],
    detected_ids: set[int],
) -> list[EntityCandidate]:
    """Merge one product-specific catalog mapping into candidates."""
    result = list(candidates)

    _LOGGER.info(
        "Matched %s LocalTuya catalog mapping %s "
        "for product %s",
        getattr(
            catalog_match,
            "source",
            "remote",
        ),
        catalog_match.mapping_id,
        catalog_match.product_id,
    )

    for catalog_entity in catalog_match.entities:
        config = copy.deepcopy(
            catalog_entity["config"]
        )

        override_keys = set(
            catalog_entity.get(
                "override_keys",
                (),
            )
        )

        platform = catalog_entity[
            "platform"
        ]

        primary_dp = config.get(
            CONF_ID
        )

        try:
            primary_dp = int(
                primary_dp
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        # Primary entity DP must always exist on LAN.
        if primary_dp not in detected_ids:
            continue

        config[CONF_ID] = primary_dp
        config[CONF_PLATFORM] = platform

        if not config.get(
            CONF_FRIENDLY_NAME
        ):
            device_label = str(
                mapper_device.get("name")
                or mapper_device.get(
                    "product_name"
                )
                or mapper_device.get(
                    "productName"
                )
                or "Tuya Device"
            )

            config[
                CONF_FRIENDLY_NAME
            ] = (
                f"{device_label} "
                f"{platform.replace('_', ' ').title()} "
                f"DP {primary_dp}"
            )

        catalog_marker = (
            f"catalog:"
            f"{catalog_match.mapping_id}"
        )

        catalog_refs = list(
            catalog_match.required_dps
        )

        if primary_dp not in catalog_refs:
            catalog_refs.append(
                primary_dp
            )

        existing_index = next(
            (
                index
                for index, candidate
                in enumerate(result)
                if (
                    candidate.platform
                    == platform
                    and candidate.primary_dp
                    == primary_dp
                )
            ),
            None,
        )

        # ----------------------------------------------------
        # Merge catalog knowledge into an existing
        # generic candidate.
        # ----------------------------------------------------
        if existing_index is not None:
            existing = result[
                existing_index
            ]

            merged_config = dict(
                existing.config
            )

            override_applied = False

            for (
                config_key,
                config_value,
            ) in config.items():
                if config_key in {
                    CONF_ID,
                    CONF_PLATFORM,
                    CONF_FRIENDLY_NAME,
                }:
                    continue

                # Generic/built-in knowledge wins by default.
                # Replacement is allowed only when the catalog
                # explicitly declares override_keys.
                if (
                    config_key
                    in override_keys
                    and config_key
                    in merged_config
                ):
                    if (
                        merged_config[
                            config_key
                        ]
                        != config_value
                    ):
                        merged_config[
                            config_key
                        ] = config_value

                        override_applied = (
                            True
                        )

                    continue

                # Product-specific catalog knowledge may safely
                # add values not known by the generic mapper.
                merged_config.setdefault(
                    config_key,
                    config_value,
                )

            referenced_dps = list(
                existing.referenced_dps
                or (
                    existing.primary_dp,
                )
            )

            for dp_id in catalog_refs:
                if (
                    dp_id
                    not in referenced_dps
                ):
                    referenced_dps.append(
                        dp_id
                    )

            matched_codes = list(
                existing.matched_codes
            )

            if (
                catalog_marker
                not in matched_codes
            ):
                matched_codes.append(
                    catalog_marker
                )

            if (
                catalog_match.confidence
                in {
                    "verified",
                    "community",
                }
            ):
                # Exact product-specific knowledge validated
                # against observed LAN DPS is HIGH confidence.
                merged_confidence = (
                    MappingConfidence.HIGH
                )

            elif override_applied:
                # Experimental replacement requires explicit
                # approval in the review UI.
                merged_confidence = (
                    MappingConfidence.MEDIUM
                )

            else:
                merged_confidence = (
                    existing.confidence
                )

            result[
                existing_index
            ] = EntityCandidate(
                platform=(
                    existing.platform
                ),
                primary_dp=(
                    existing.primary_dp
                ),
                confidence=(
                    merged_confidence
                ),
                config=merged_config,
                matched_codes=tuple(
                    matched_codes
                ),
                referenced_dps=tuple(
                    referenced_dps
                ),
            )

            continue

        # ----------------------------------------------------
        # Catalog-only entity.
        # ----------------------------------------------------
        confidence = (
            MappingConfidence.HIGH
            if catalog_match.confidence
            in {
                "verified",
                "community",
            }
            else MappingConfidence.MEDIUM
        )

        result.append(
            EntityCandidate(
                platform=platform,
                primary_dp=primary_dp,
                confidence=confidence,
                config=config,
                matched_codes=(
                    catalog_marker,
                ),
                referenced_dps=tuple(
                    catalog_refs
                ),
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
        catalog_match = (
            catalog_client.match(
                mapper_device,
                detected_ids,
            )
        )

        if catalog_match is not None:
            candidates = (
                _merge_catalog_match(
                    candidates,
                    catalog_match,
                    mapper_device,
                    detected_ids,
                )
            )

    accepted: list[
        EntityCandidate
    ] = []

    for candidate in candidates:
        if (
            candidate.confidence
            == MappingConfidence.LOW
        ):
            continue

        referenced_dps = (
            candidate.referenced_dps
            or (
                candidate.primary_dp,
            )
        )

        # LAN remains authoritative for every source:
        # generic metadata, bundled catalog and remote catalog.
        if not set(
            referenced_dps
        ).issubset(
            detected_ids
        ):
            _LOGGER.debug(
                "Ignoring mapping candidate %s DP %s: "
                "referenced DPS %s not all detected over LAN",
                candidate.platform,
                candidate.primary_dp,
                referenced_dps,
            )
            continue

        accepted.append(
            candidate
        )

    return sorted(
        accepted,
        key=lambda candidate: (
            candidate.platform,
            candidate.primary_dp,
        ),
    )
