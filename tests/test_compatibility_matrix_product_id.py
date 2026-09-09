"""Product ID normalization for compatibility matrix."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityProductIdTests(unittest.TestCase):
    def test_blank_product_id_is_skipped(self):
        self.assertEqual(
            build_compatibility_matrix([
                CompatibilityRecord("", "dj", "3.5", "map", "verified", True, "direct")
            ]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
