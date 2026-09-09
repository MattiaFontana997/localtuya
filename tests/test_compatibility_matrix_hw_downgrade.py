"""Verified catalog confidence without hardware evidence is downgraded publicly."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityHardwareDowngradeTests(unittest.TestCase):
    def test_verified_without_hardware_is_community(self):
        row = CompatibilityRecord("p", "dj", "3.5", "m", "verified", False, "direct").public_dict()
        self.assertEqual(row["status"], "community")


if __name__ == "__main__":
    unittest.main()
