"""Reason code for duplicate primary DP."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigDuplicateReasonTests(unittest.TestCase):
    def test_duplicate_primary_reason_is_stable(self):
        candidates = [
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 1}),
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 1}),
        ]
        self.assertEqual(evaluate_zero_config(candidates).reason, "ambiguous_primary_dp")


if __name__ == "__main__":
    unittest.main()
