"""Zero primary datapoint is not auto-configurable."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigZeroPrimaryTests(unittest.TestCase):
    def test_zero_primary_requires_review(self):
        candidate = SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 0})
        self.assertEqual(evaluate_zero_config([candidate]).decision, ZeroConfigDecision.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
