"""Fail-closed zero-config onboarding decisions for LocalTuya."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable


class ZeroConfigDecision(str, Enum):
    """Outcome of automatic mapping eligibility evaluation."""

    AUTO_CONFIGURE = "auto_configure"
    REVIEW_REQUIRED = "review_required"
    MANUAL_REQUIRED = "manual_required"


@dataclass(slots=True, frozen=True)
class ZeroConfigResult:
    """Result of one zero-config eligibility evaluation."""

    decision: ZeroConfigDecision
    entities: list[dict[str, Any]]
    reason: str


def _confidence_value(candidate: Any) -> str:
    confidence = getattr(candidate, "confidence", None)
    value = getattr(confidence, "value", confidence)
    return str(value or "").strip().lower()



def evaluate_prepared_zero_config(
    device_data: dict[str, Any],
    review_candidates: Iterable[Any],
) -> ZeroConfigResult:
    """Decide whether an already prepared QR device may be silently persisted.

    ``async_prepare_qr_device`` has already put deterministic HIGH mappings in
    ``device_data['entities']`` and left MEDIUM mappings in
    ``review_candidates``. Both single and bulk QR onboarding use this one
    fail-closed decision point.
    """
    review_candidates = list(review_candidates or [])
    if review_candidates:
        return ZeroConfigResult(
            ZeroConfigDecision.REVIEW_REQUIRED,
            [],
            "mapping_review_required",
        )

    if not isinstance(device_data, dict):
        return ZeroConfigResult(
            ZeroConfigDecision.MANUAL_REQUIRED,
            [],
            "invalid_device_data",
        )
    entities = device_data.get("entities")
    if not isinstance(entities, list) or not entities:
        return ZeroConfigResult(
            ZeroConfigDecision.MANUAL_REQUIRED,
            [],
            "no_candidates",
        )

    normalized: list[dict[str, Any]] = []
    seen_primary: set[int] = set()
    for config in entities:
        if not isinstance(config, dict) or not config:
            return ZeroConfigResult(
                ZeroConfigDecision.REVIEW_REQUIRED,
                [],
                "invalid_candidate_config",
            )
        raw_primary = config.get("id")
        if isinstance(raw_primary, bool):
            return ZeroConfigResult(
                ZeroConfigDecision.REVIEW_REQUIRED,
                [],
                "invalid_primary_dp",
            )
        try:
            primary = int(raw_primary)
        except (TypeError, ValueError):
            return ZeroConfigResult(
                ZeroConfigDecision.REVIEW_REQUIRED,
                [],
                "invalid_primary_dp",
            )
        if primary <= 0 or primary in seen_primary:
            return ZeroConfigResult(
                ZeroConfigDecision.REVIEW_REQUIRED,
                [],
                "ambiguous_primary_dp",
            )
        seen_primary.add(primary)
        normalized.append(copy.deepcopy(config))

    return ZeroConfigResult(
        ZeroConfigDecision.AUTO_CONFIGURE,
        normalized,
        "prepared_high_confidence_entities",
    )

def evaluate_zero_config(candidates: Iterable[Any]) -> ZeroConfigResult:
    """Return whether candidates can be persisted without user mapping review.

    Zero-config is intentionally conservative: every candidate must be high
    confidence, each entity must expose a unique primary DP, and every config
    must be a non-empty dictionary. Anything less is routed to review/manual
    configuration instead of guessing.
    """
    candidates = list(candidates or [])
    if not candidates:
        return ZeroConfigResult(
            ZeroConfigDecision.MANUAL_REQUIRED,
            [],
            "no_candidates",
        )

    configs: list[dict[str, Any]] = []
    seen_primary: set[int] = set()

    for candidate in candidates:
        if _confidence_value(candidate) != "high":
            return ZeroConfigResult(
                ZeroConfigDecision.REVIEW_REQUIRED,
                [],
                "non_high_confidence_candidate",
            )

        config = getattr(candidate, "config", None)
        if not isinstance(config, dict) or not config:
            return ZeroConfigResult(
                ZeroConfigDecision.REVIEW_REQUIRED,
                [],
                "invalid_candidate_config",
            )

        raw_primary = config.get("id")
        if isinstance(raw_primary, bool):
            return ZeroConfigResult(
                ZeroConfigDecision.REVIEW_REQUIRED,
                [],
                "invalid_primary_dp",
            )
        try:
            primary = int(raw_primary)
        except (TypeError, ValueError):
            return ZeroConfigResult(
                ZeroConfigDecision.REVIEW_REQUIRED,
                [],
                "invalid_primary_dp",
            )
        if primary <= 0 or primary in seen_primary:
            return ZeroConfigResult(
                ZeroConfigDecision.REVIEW_REQUIRED,
                [],
                "ambiguous_primary_dp",
            )
        seen_primary.add(primary)
        configs.append(copy.deepcopy(config))

    return ZeroConfigResult(
        ZeroConfigDecision.AUTO_CONFIGURE,
        configs,
        "all_candidates_high_confidence",
    )
