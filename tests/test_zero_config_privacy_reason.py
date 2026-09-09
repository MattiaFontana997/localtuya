"""Zero-config reason codes never contain device-specific data."""

from __future__ import annotations

import unittest

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigReasonPrivacyTests(unittest.TestCase):
    def test_no_candidate_reason_is_generic(self):
        self.assertEqual(evaluate_zero_config([]).reason, "no_candidates")


if __name__ == "__main__":
    unittest.main()
