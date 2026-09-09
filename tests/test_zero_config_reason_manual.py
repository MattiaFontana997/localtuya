"""Manual-required zero-config decisions keep a stable reason."""

from __future__ import annotations

import unittest

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigManualReasonTests(unittest.TestCase):
    def test_no_candidates_is_manual_required(self):
        result = evaluate_zero_config([])
        self.assertIs(result.decision, ZeroConfigDecision.MANUAL_REQUIRED)
        self.assertEqual(result.reason, "no_candidates")


if __name__ == "__main__":
    unittest.main()
