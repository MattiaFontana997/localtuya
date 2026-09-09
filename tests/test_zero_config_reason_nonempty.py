"""Every zero-config decision carries a non-empty reason."""

from __future__ import annotations

import unittest

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigReasonNonemptyTests(unittest.TestCase):
    def test_manual_reason_nonempty(self):
        self.assertTrue(evaluate_zero_config([]).reason)


if __name__ == "__main__":
    unittest.main()
