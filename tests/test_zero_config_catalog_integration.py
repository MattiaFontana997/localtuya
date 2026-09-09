"""Zero-config integration with catalog authority semantics."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigCatalogIntegrationTests(unittest.TestCase):
    def test_verified_catalog_candidate_can_auto_configure(self):
        candidate = SimpleNamespace(
            confidence=SimpleNamespace(value="high"),
            trust=SimpleNamespace(value="verified"),
            config={"id": 20, "platform": "light"},
        )
        result = evaluate_zero_config([candidate])
        self.assertEqual(result.decision, ZeroConfigDecision.AUTO_CONFIGURE)

    def test_ambiguous_candidate_set_never_auto_configures(self):
        candidates = [
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 20, "platform": "light"}),
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 20, "platform": "switch"}),
        ]
        result = evaluate_zero_config(candidates)
        self.assertEqual(result.decision, ZeroConfigDecision.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
