"""Acceptance tests for zero-config onboarding decisions."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import (
    ZeroConfigDecision,
    evaluate_zero_config,
)


class ZeroConfigTests(unittest.TestCase):
    """Verify fail-closed zero-config eligibility."""

    def test_all_high_confidence_candidates_are_auto_configurable(self):
        candidates = [
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 1}),
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 2}),
        ]
        result = evaluate_zero_config(candidates)
        self.assertEqual(result.decision, ZeroConfigDecision.AUTO_CONFIGURE)
        self.assertEqual(len(result.entities), 2)

    def test_medium_candidate_requires_review(self):
        candidates = [
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 1}),
            SimpleNamespace(confidence=SimpleNamespace(value="medium"), config={"id": 2}),
        ]
        result = evaluate_zero_config(candidates)
        self.assertEqual(result.decision, ZeroConfigDecision.REVIEW_REQUIRED)
        self.assertEqual(result.entities, [])

    def test_no_candidates_requires_manual_mapping(self):
        result = evaluate_zero_config([])
        self.assertEqual(result.decision, ZeroConfigDecision.MANUAL_REQUIRED)

    def test_duplicate_primary_dp_fails_closed(self):
        candidates = [
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 1}),
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 1}),
        ]
        result = evaluate_zero_config(candidates)
        self.assertEqual(result.decision, ZeroConfigDecision.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
