"""Zero-config detects duplicate DPs after integer normalization."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigNormalizedDuplicateTests(unittest.TestCase):
    def test_string_and_integer_same_dp_are_ambiguous(self):
        candidates = [SimpleNamespace(confidence="high", config={"id": "1"}), SimpleNamespace(confidence="high", config={"id": 1})]
        self.assertEqual(evaluate_zero_config(candidates).decision, ZeroConfigDecision.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
