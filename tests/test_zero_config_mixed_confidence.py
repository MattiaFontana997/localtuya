"""One non-high candidate prevents silent zero-config persistence."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigMixedConfidenceTests(unittest.TestCase):
    def test_mixed_high_medium_requires_review(self):
        candidates = [SimpleNamespace(confidence="high", config={"id": 1}), SimpleNamespace(confidence="medium", config={"id": 2})]
        self.assertIs(evaluate_zero_config(candidates).decision, ZeroConfigDecision.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
