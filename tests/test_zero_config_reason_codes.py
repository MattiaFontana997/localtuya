"""Stable privacy-safe reason codes for zero-config decisions."""

from __future__ import annotations

import unittest

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigReasonCodeTests(unittest.TestCase):
    def test_empty_candidates_has_stable_reason(self):
        result = evaluate_zero_config([])
        self.assertEqual(result.decision, ZeroConfigDecision.MANUAL_REQUIRED)
        self.assertEqual(result.reason, "no_candidates")


if __name__ == "__main__":
    unittest.main()
