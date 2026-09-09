"""Product ID is intentionally public compatibility metadata."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityPublicProductIdTests(unittest.TestCase):
    def test_product_id_is_public(self):
        row = CompatibilityRecord("product-123", "dj", "3.5", "m", "community", True, "direct").public_dict()
        self.assertEqual(row["product_id"], "product-123")


if __name__ == "__main__":
    unittest.main()
