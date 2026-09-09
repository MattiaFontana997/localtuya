"""No candidates require manual mapping."""

from __future__ import annotations

import unittest

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigEmptyManualTests(unittest.TestCase):
    def test_empty_candidates_manual(self):
        self.assertIs(evaluate_zero_config([]).decision, ZeroConfigDecision.MANUAL_REQUIRED)


if __name__ == "__main__":
    unittest.main()
