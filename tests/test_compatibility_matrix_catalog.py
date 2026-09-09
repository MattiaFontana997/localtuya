"""Catalog-to-matrix compatibility evidence tests."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import build_compatibility_matrix, records_from_catalog


class CompatibilityMatrixCatalogTests(unittest.TestCase):
    def test_catalog_compatibility_metadata_generates_public_row(self):
        catalog = {
            "mappings": [
                {
                    "id": "map-1",
                    "confidence": "verified",
                    "match": {"product_ids": ["prod-1"], "category": "dj"},
                    "compatibility": {
                        "hardware_tested": True,
                        "protocols": ["3.5"],
                        "transport": "direct",
                        "home_assistant": "2026.9",
                        "localtuya": "6.7.0-dev",
                        "tested_at": "2026-09-09",
                    },
                }
            ]
        }
        rows = build_compatibility_matrix(records_from_catalog(catalog))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "verified")
        self.assertEqual(rows[0]["protocol"], "3.5")
        self.assertEqual(rows[0]["transport"], "direct")

    def test_mapping_without_compatibility_evidence_is_not_published(self):
        catalog = {
            "mappings": [
                {
                    "id": "map-1",
                    "confidence": "verified",
                    "match": {"product_ids": ["prod-1"], "category": "dj"},
                }
            ]
        }
        self.assertEqual(records_from_catalog(catalog), [])


if __name__ == "__main__":
    unittest.main()
