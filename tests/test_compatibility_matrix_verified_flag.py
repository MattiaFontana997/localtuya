"""Verified compatibility status requires real hardware evidence."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityVerifiedFlagTests(unittest.TestCase):
    def test_verified_with_hardware_stays_verified(self):
        row = CompatibilityRecord("p", "dj", "3.5", "m", "verified", True, "direct").public_dict()
        self.assertEqual(row["status"], "verified")


if __name__ == "__main__":
    unittest.main()
