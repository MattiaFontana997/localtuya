"""Catalog mappings without product IDs do not create public matrix rows."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import records_from_catalog


class CompatibilityEmptyProductsTests(unittest.TestCase):
    def test_empty_product_ids_yield_no_records(self):
        records = records_from_catalog({"mappings": [{
            "id": "m", "confidence": "community",
            "match": {"product_ids": [], "category": "dj"},
            "compatibility": {"hardware_tested": True, "protocols": ["3.5"], "transport": "direct"},
        }]})
        self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main()
