"""Integration tests for bulk onboarding and zero-config decisions."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class BulkZeroConfigIntegrationTests(unittest.TestCase):
    """Bulk onboarding must auto-save only deterministic mappings."""

    def test_high_confidence_device_needs_no_mapping_review(self):
        candidates = [
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 20, "platform": "light"}),
        ]
        result = evaluate_zero_config(candidates)
        self.assertEqual(result.decision, ZeroConfigDecision.AUTO_CONFIGURE)
        self.assertEqual(result.entities[0]["platform"], "light")

    def test_medium_confidence_device_stays_out_of_silent_bulk_save(self):
        candidates = [
            SimpleNamespace(confidence=SimpleNamespace(value="medium"), config={"id": 20, "platform": "light"}),
        ]
        result = evaluate_zero_config(candidates)
        self.assertEqual(result.decision, ZeroConfigDecision.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
