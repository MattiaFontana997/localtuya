"""High confidence remains the zero-config threshold."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigHighConfidenceTests(unittest.TestCase):
    def test_high_confidence_candidate_auto_configures(self):
        candidate = SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 1})
        self.assertEqual(evaluate_zero_config([candidate]).decision, ZeroConfigDecision.AUTO_CONFIGURE)


if __name__ == "__main__":
    unittest.main()
