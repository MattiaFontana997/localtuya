"""Invalid primary-DP behavior for zero-config."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigInvalidPrimaryTests(unittest.TestCase):
    def test_boolean_primary_dp_requires_review(self):
        candidate = SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": True})
        self.assertEqual(evaluate_zero_config([candidate]).decision, ZeroConfigDecision.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
