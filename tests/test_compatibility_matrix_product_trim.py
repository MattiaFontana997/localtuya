"""Compatibility matrix trims surrounding Product ID whitespace."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityProductTrimTests(unittest.TestCase):
    def test_product_id_is_trimmed(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("  prod  ", "dj", "3.5", "m", "community", True, "direct")
        ])[0]
        self.assertEqual(row["product_id"], "prod")


if __name__ == "__main__":
    unittest.main()
