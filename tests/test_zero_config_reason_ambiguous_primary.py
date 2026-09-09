"""Ambiguous primary DP uses the stable zero-config reason."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigAmbiguousPrimaryReasonTests(unittest.TestCase):
    def test_duplicate_dp_reason(self):
        candidates = [SimpleNamespace(confidence="high", config={"id": 1}), SimpleNamespace(confidence="high", config={"id": 1})]
        self.assertEqual(evaluate_zero_config(candidates).reason, "ambiguous_primary_dp")


if __name__ == "__main__":
    unittest.main()
