"""One catalog mapping can publish compatibility for product aliases."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import records_from_catalog


class CompatibilityMultipleProductsTests(unittest.TestCase):
    def test_product_aliases_create_distinct_records(self):
        records = records_from_catalog({"mappings": [{
            "id": "m", "confidence": "community",
            "match": {"product_ids": ["p1", "p2"], "category": "dj"},
            "compatibility": {"hardware_tested": True, "protocols": ["3.5"], "transport": "direct"},
        }]})
        self.assertEqual([r.product_id for r in records], ["p1", "p2"])


if __name__ == "__main__":
    unittest.main()
