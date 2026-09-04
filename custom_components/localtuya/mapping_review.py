"""Review mapping updates for already configured LocalTuya devices."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from typing import Any

from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    CONF_ID,
    CONF_PLATFORM,
)

from .device_mapper import (
    EntityCandidate,
    MappingConfidence,
)


_PROTECTED_KEYS = {
    CONF_ID,
    CONF_PLATFORM,
    CONF_FRIENDLY_NAME,
}


class MappingReviewKind(str, Enum):
    """Kind of change proposed for an existing device."""

    CURRENT = "current"
    UPDATE = "update"
    NEW = "new"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class ExistingMappingReview:
    """One mapping comparison result."""

    key: str
    kind: MappingReviewKind
    candidate: EntityCandidate
    existing_index: int | None
    changed_keys: tuple[str, ...]
    proposed_config: dict[str, Any]

    @property
    def actionable(self) -> bool:
        """Return whether applying this review would change configuration."""
        return self.kind in {
            MappingReviewKind.UPDATE,
            MappingReviewKind.NEW,
        }


def mapping_review_key(
    candidate: EntityCandidate,
) -> str:
    """Return stable review key for one candidate."""
    return (
        f"{candidate.platform}:"
        f"{candidate.primary_dp}"
    )


def _entity_identity(
    entity: dict[str, Any],
) -> tuple[str, int] | None:
    """Return comparable platform/DP identity."""
    platform = entity.get(
        CONF_PLATFORM
    )

    if not isinstance(
        platform,
        str,
    ):
        return None

    raw_dp = entity.get(
        CONF_ID
    )

    if isinstance(
        raw_dp,
        bool,
    ):
        return None

    try:
        dp_id = int(
            raw_dp
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    if dp_id <= 0:
        return None

    return (
        platform,
        dp_id,
    )


def build_existing_mapping_reviews(
    existing_entities: list[dict[str, Any]],
    candidates: list[EntityCandidate],
) -> list[ExistingMappingReview]:
    """Compare current entities against resolved mapping candidates."""
    existing_by_identity: dict[
        tuple[str, int],
        int,
    ] = {}

    existing_by_dp: dict[
        int,
        int,
    ] = {}

    for (
        index,
        entity,
    ) in enumerate(
        existing_entities
    ):
        identity = (
            _entity_identity(
                entity
            )
        )

        if identity is None:
            continue

        # Existing configuration should normally contain
        # unique platform/DP identities. Keep the first one
        # if legacy data contains a duplicate.
        existing_by_identity.setdefault(
            identity,
            index,
        )

        existing_by_dp.setdefault(
            identity[1],
            index,
        )

    reviews: list[
        ExistingMappingReview
    ] = []

    seen_candidate_keys: set[
        str
    ] = set()

    for candidate in candidates:
        review_key = (
            mapping_review_key(
                candidate
            )
        )

        # Resolver output should already be unique, but keep
        # the review layer deterministic if malformed data
        # ever reaches it.
        if (
            review_key
            in seen_candidate_keys
        ):
            continue

        seen_candidate_keys.add(
            review_key
        )

        identity = (
            candidate.platform,
            candidate.primary_dp,
        )

        existing_index = (
            existing_by_identity.get(
                identity
            )
        )

        # LocalTuya entity identity is DP-based. A candidate
        # using an already configured DP with another platform
        # must never be added automatically.
        if (
            existing_index is None
            and candidate.primary_dp
            in existing_by_dp
        ):
            proposed = copy.deepcopy(
                candidate.config
            )

            proposed[
                CONF_ID
            ] = candidate.primary_dp

            proposed[
                CONF_PLATFORM
            ] = candidate.platform

            reviews.append(
                ExistingMappingReview(
                    key=review_key,
                    kind=(
                        MappingReviewKind.CONFLICT
                    ),
                    candidate=candidate,
                    existing_index=(
                        existing_by_dp[
                            candidate.primary_dp
                        ]
                    ),
                    changed_keys=(),
                    proposed_config=proposed,
                )
            )

            continue

        if existing_index is None:
            proposed = copy.deepcopy(
                candidate.config
            )

            proposed[
                CONF_ID
            ] = candidate.primary_dp

            proposed[
                CONF_PLATFORM
            ] = candidate.platform

            reviews.append(
                ExistingMappingReview(
                    key=review_key,
                    kind=(
                        MappingReviewKind.NEW
                    ),
                    candidate=candidate,
                    existing_index=None,
                    changed_keys=(),
                    proposed_config=proposed,
                )
            )

            continue

        existing = (
            existing_entities[
                existing_index
            ]
        )

        proposed = copy.deepcopy(
            existing
        )

        changed_keys: list[str] = []

        for (
            config_key,
            candidate_value,
        ) in candidate.config.items():
            if (
                config_key
                in _PROTECTED_KEYS
            ):
                continue

            current_value = (
                existing.get(
                    config_key
                )
            )

            if (
                config_key in existing
                and current_value
                == candidate_value
            ):
                continue

            proposed[
                config_key
            ] = copy.deepcopy(
                candidate_value
            )

            changed_keys.append(
                config_key
            )

        kind = (
            MappingReviewKind.UPDATE
            if changed_keys
            else MappingReviewKind.CURRENT
        )

        reviews.append(
            ExistingMappingReview(
                key=review_key,
                kind=kind,
                candidate=candidate,
                existing_index=(
                    existing_index
                ),
                changed_keys=tuple(
                    sorted(
                        changed_keys
                    )
                ),
                proposed_config=proposed,
            )
        )

    return reviews


def default_existing_mapping_selection(
    reviews: list[ExistingMappingReview],
) -> list[str]:
    """Return safe default selection for review UI."""
    return [
        review.key
        for review in reviews
        if (
            review.actionable
            and review.candidate.confidence
            == MappingConfidence.HIGH
        )
    ]


def apply_existing_mapping_reviews(
    existing_entities: list[dict[str, Any]],
    reviews: list[ExistingMappingReview],
    selected_keys: set[str],
) -> list[dict[str, Any]]:
    """Apply explicitly selected mapping changes conservatively."""
    result = copy.deepcopy(
        existing_entities
    )

    selected = {
        review.key:
            review
        for review in reviews
        if (
            review.key
            in selected_keys
            and review.actionable
        )
    }

    # Update current entities first so indexes remain stable.
    for review in selected.values():
        if (
            review.kind
            != MappingReviewKind.UPDATE
        ):
            continue

        if (
            review.existing_index
            is None
        ):
            continue

        result[
            review.existing_index
        ] = copy.deepcopy(
            review.proposed_config
        )

    # New candidates are appended. Existing entities are
    # never removed by mapping review.
    for review in selected.values():
        if (
            review.kind
            != MappingReviewKind.NEW
        ):
            continue

        result.append(
            copy.deepcopy(
                review.proposed_config
            )
        )

    return result
