"""Zero-config rejects empty entity configs."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigEmptyConfigTests(unittest.TestCase):
    def test_empty_candidate_config_requires_review(self):
        candidate = SimpleNamespace(confidence=SimpleNamespace(value="high"), config={})
        self.assertEqual(evaluate_zero_config([candidate]).decision, ZeroConfigDecision.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
