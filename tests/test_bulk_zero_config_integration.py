"""Integration tests for prepared zero-config decisions used by bulk onboarding."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from homeassistant.const import CONF_ENTITIES

from custom_components.localtuya.zero_config import (
    ZeroConfigDecision,
    evaluate_prepared_zero_config,
    evaluate_zero_config,
)


class BulkZeroConfigIntegrationTests(unittest.TestCase):
    def test_high_candidate_engine_remains_auto_configurable(self):
        result = evaluate_zero_config([
            SimpleNamespace(
                confidence=SimpleNamespace(value="high"),
                config={"id": 20, "platform": "light"},
            )
        ])
        self.assertEqual(result.decision, ZeroConfigDecision.AUTO_CONFIGURE)

    def test_prepared_high_entities_need_no_review(self):
        result = evaluate_prepared_zero_config(
            {CONF_ENTITIES: [{"id": 20, "platform": "light"}]},
            [],
        )
        self.assertEqual(result.decision, ZeroConfigDecision.AUTO_CONFIGURE)
        self.assertEqual(result.entities[0]["platform"], "light")

    def test_medium_candidate_blocks_silent_save(self):
        result = evaluate_prepared_zero_config(
            {CONF_ENTITIES: [{"id": 20, "platform": "light"}]},
            [SimpleNamespace(confidence=SimpleNamespace(value="medium"))],
        )
        self.assertEqual(result.decision, ZeroConfigDecision.REVIEW_REQUIRED)
        self.assertEqual(result.entities, [])

    def test_no_prepared_entities_requires_manual_mapping(self):
        result = evaluate_prepared_zero_config({CONF_ENTITIES: []}, [])
        self.assertEqual(result.decision, ZeroConfigDecision.MANUAL_REQUIRED)


if __name__ == "__main__":
    unittest.main()
