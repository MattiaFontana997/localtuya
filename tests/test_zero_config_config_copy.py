"""Zero-config config isolation."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigConfigIsolationTests(unittest.TestCase):
    def test_mutating_source_after_decision_does_not_change_result(self):
        config = {"id": 1, "platform": "switch"}
        candidate = SimpleNamespace(confidence=SimpleNamespace(value="high"), config=config)
        result = evaluate_zero_config([candidate])
        config["platform"] = "light"
        self.assertEqual(result.entities[0]["platform"], "switch")


if __name__ == "__main__":
    unittest.main()
