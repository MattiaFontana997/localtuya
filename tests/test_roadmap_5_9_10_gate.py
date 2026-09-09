"""Final acceptance gate for roadmap items 5, 9 and 10."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix
from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class Roadmap5910Gate(unittest.TestCase):
    def test_compatibility_verified_requires_hardware_evidence(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("p", "dj", "3.5", "m", "verified", False, "direct")
        ])[0]
        self.assertEqual(row["status"], "community")

    def test_zero_config_is_fail_closed(self):
        self.assertEqual(evaluate_zero_config([]).decision, ZeroConfigDecision.MANUAL_REQUIRED)


if __name__ == "__main__":
    unittest.main()
