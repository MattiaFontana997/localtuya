"""Compatibility matrix preserves public Tuya category metadata."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityCategoryPreserveTests(unittest.TestCase):
    def test_category_is_preserved(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("p", "wk", "3.5", "m", "community", True, "direct")
        ])[0]
        self.assertEqual(row["category"], "wk")


if __name__ == "__main__":
    unittest.main()
