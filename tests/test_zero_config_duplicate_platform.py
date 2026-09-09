"""Additional ambiguity regression for zero-config."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigDuplicatePlatformTests(unittest.TestCase):
    def test_same_dp_two_platforms_requires_review(self):
        candidates = [
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 1, "platform": "switch"}),
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 1, "platform": "binary_sensor"}),
        ]
        self.assertEqual(evaluate_zero_config(candidates).decision, ZeroConfigDecision.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
